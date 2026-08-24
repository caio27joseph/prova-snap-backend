# Parte 4 — Trade-offs de Engenharia: 3 melhorias para a próxima release

O time tem capacidade para **3 melhorias** da lista de 10 do enunciado. A
decisão abaixo não foi tomada no abstrato: foi tomada **com o código entregue
na mesa** — cada escolha cita uma dor real e documentada deste repositório, e
a análise de incidente da Parte 3 ([PARTE3_INCIDENT.md](PARTE3_INCIDENT.md))
funciona como dado de priorização, não como exercício separado.

**As escolhidas: (1) busca textual avançada (full-text search / `pg_trgm`),
(2) paginação dos resultados, (3) observabilidade (OpenTelemetry) — nesta
ordem.**

---

## 1. Quais 3 e por quê

### 1.1 Busca textual avançada (`pg_trgm` / full-text search)

**A dor:** nossa busca usa `ILIKE '%termo%'` nas três strategies
(`app/services/search/analytics.py` em `content`, `investigator.py` em `name`,
`case_manager.py` em `title`) — e `%termo%` **não usa B-tree**: é seq scan por
construção. Isso foi uma decisão consciente de escopo, não um descuido: o
enunciado exclui "busca otimizada" e os índices ficaram só nas colunas de
filtro (Decisão 4 do [AI_ENGINEERING_LOG.md](../AI_ENGINEERING_LOG.md);
[ESCALABILIDADE.md](ESCALABILIDADE.md) já a lista como gargalo conhecido).

**A evidência de prioridade:** a Parte 3 é literalmente a simulação do que
acontece quando esse design encontra carga real — a Hipótese 1 do incidente é
o `ILIKE` saturando a CPU do banco, e o detalhe que agrava: o
`SEARCH_RESULT_LIMIT = 50` (`app/config.py`) **limita linhas retornadas, não
linhas varridas**; um usuário com 3 permissões dispara 3 varreduras completas
por requisição. A prevenção nº 3 do incidente diz explicitamente: "o incidente
é o dado de priorização que faltava" para promover o FTS na fila.

**O remédio:** índice GIN com `pg_trgm` nas três colunas de texto — atende o
`ILIKE '%termo%'` existente **sem mudar o contrato do endpoint** — avaliando
em seguida `tsvector`/FTS para busca por relevância linguística. Criação com
`CREATE INDEX CONCURRENTLY` + `ANALYZE`, aplicando a lição da prevenção nº 2
do próprio incidente.

### 1.2 Paginação dos resultados

**A dor:** hoje nenhuma busca devolve mais que o LIMIT interno fixo de 50 —
uma guarda de recurso, não uma UX: o 51º resultado é simplesmente
inalcançável.

**Por que é a melhoria mais barata da lista:** o schema **já é cursor-ready
por desenho** (Decisão 5): PKs UUIDv7 ordenáveis por tempo tornam
`WHERE id > :cursor ORDER BY id LIMIT :n` um cursor keyset estável sob
inserções concorrentes, e o envelope de resposta já carrega o campo — cada
seção retorna `next_cursor: str | None = None` (`app/schemas/search.py`). O
custo residual, documentado em [ESCALABILIDADE.md](ESCALABILIDADE.md), é só o
endpoint: aceitar `cursor` no body do POST (um dos motivos da escolha de POST
na Decisão 4) e devolver o `id` do último item. Zero migração de schema. É o
maior valor por hora do backlog — a preparação já foi paga.

**Detalhes já decididos:** cursor **por seção** (investigator e case-manager
paginam independentemente, pois os shapes diferem); **Analytics não pagina**
(retorna agregados `total_matched`/`by_month`, não linhas).

### 1.3 Observabilidade (OpenTelemetry)

**A dor:** a Parte 3 obrigou uma admissão honesta (seção 5 do incidente): a
stack **não tem APM, tracing nem dashboards** — detectaríamos o incidente pelo
sintoma na plataforma, não por um alerta nosso, e a investigação inteira se
apoiaria em ferramentas manuais do Postgres (`pg_stat_statements`, `EXPLAIN`).
Além disso, falha de escrita de auditoria hoje existe **apenas no log de
aplicação** (`logger.exception` em `app/services/audit.py`) — numa plataforma
forense, em que a trilha é produto (Decisão 6), isso precisa virar métrica com
alerta, não linha de log que ninguém lê.

**O que instrumentar primeiro:** latência p95/p99 **por endpoint**; spans de
query no banco (separa "a busca está lenta" de "o banco está saturado");
contador de falhas de auditoria; alertas de p95 e de CPU do banco — exatamente
as lacunas que a seção 7 do incidente lista como prevenção.

---

## 2. Ordem de execução

**FTS → Paginação → Observabilidade**, e a ordem tem um argumento técnico:

1. **FTS antes de paginação:** paginar uma varredura lenta continua sendo uma
   varredura lenta — cada página de um `ILIKE` sem índice re-varre a tabela até
   satisfazer o cursor. Paginação por cima do seq scan até *amplia* o número de
   varreduras (N páginas ≈ N scans). Primeiro remove-se o scan, depois
   fatia-se o resultado. O inverso entregaria uma feature nova em cima do
   gargalo documentado.
2. **Paginação em seguida:** com índice embaixo, a implementação é pequena
   (seção 1.2) e destrava o consumo real dos resultados.
3. **Observabilidade por último na release — mas não opcional:** não depende
   das outras duas e poderia ser paralela; vem na sequência porque as duas
   primeiras mudam o perfil de performance do sistema, e é exatamente esse
   novo perfil que queremos medir em produção (baseline pós-FTS, não pré).

## 3. Critérios de priorização

Os critérios são o entregável tanto quanto a escolha — explicitados, eles
podem ser auditados e reusados na próxima release:

| # | Critério | Aplicação concreta |
|---|---|---|
| 1 | **Dor real documentada > dor hipotética** | O seq scan do `ILIKE` tem dossiê: Decisão 4, ESCALABILIDADE.md e a análise da Parte 3. Rate limiting e cache resolvem dores que ainda não observamos. |
| 2 | **Custo marginal vs. valor** | Paginação está quase de graça porque o design a preparou (UUIDv7 + envelope, Decisão 5) — valor alto, custo residual mínimo. |
| 3 | **Operar o que existe antes de adicionar features** | Observabilidade não adiciona funcionalidade — adiciona a capacidade de *ver* o sistema que já entregamos. A Parte 3 mostrou que hoje voamos sem instrumentos. |

## 4. Riscos que aceitamos assumir agora

Nomeados um a um, com a mitigação temporária e o porquê da aceitabilidade:

- **Sem rate limiting.** Mitigação temporária no proxy/load balancer (a mesma
  alavanca da seção 1 do incidente), que o contexto on-premises já pressupõe.
  Aceitável porque o FTS remove a razão de cada requisição ser cara; rate
  limiting na aplicação vira prioridade se a telemetria (melhoria 3) mostrar
  abuso real.
- **Sem cache Redis.** Dados investigativos exigem consistência — servir
  resultado de busca defasado numa plataforma forense é risco de produto, não
  só técnico. E o ganho é dúbio *antes* do FTS: cachear a query lenta esconde
  o gargalo em vez de removê-lo. Reavaliar com números depois das melhorias 1
  e 3.
- **Sem pipeline de CI completa.** Descrita, não implementada (o enunciado
  explicitamente aceita descrever). Risco de regressão mitigado pelo `make
  check` local (lint + suíte completa, gate de todo merge — `Makefile`) e por
  uma suíte com mais de 60 testes que cobre os caminhos de erro, não só o happy path.
- **Sem modelo de permissões mais granular.** Client roles
  (`resource_access.<client>.roles`, Decisão 2) bastam para o escopo atual; a
  camada de recurso (ownership — "viewer vê relatórios *do João*") está
  documentada na Parte 1.2 ([PARTE1_AUTH.md](PARTE1_AUTH.md)) com o caminho
  claro (`owner_id = sub` + filtro na query) para quando o requisito chegar.
- **Sem relevância/ranking.** Dependência técnica, não escolha: sem FTS não
  existe sinal de relevância para ranquear — `ILIKE` só sabe "contém ou não
  contém". Ranking é o passo *seguinte* ao FTS, impossível antes dele.

## 5. Por que cada um dos demais itens perdeu (uma linha cada)

- **Rate limiting** — mitigável no proxy sem código; ataca o sintoma cuja
  causa (custo por requisição) o FTS remove.
- **Cache Redis** — consistência é requisito forense e o ganho é ilegível
  antes de FTS + telemetria darem números.
- **Mais testes automatizados** — a suíte atual (60+ testes) já cobre os 5 casos obrigatórios e
  a matriz de erros já dão confiança proporcional ao escopo; mais testes sem
  nova superfície é rendimento decrescente.
- **Pipeline de CI** — valor real, mas replica o que o `make check` já garante
  localmente num time deste tamanho; descrita para implementação futura.
- **Permissões mais granulares** — sem requisito concreto que os client roles
  não atendam; desenho de ownership já documentado na Parte 1.2.
- **Relevância/ranking** — bloqueado tecnicamente pelo próprio FTS (seção 4).
- **Estratégia de rollback melhorada** — o raciocínio já virou runbook escrito
  na seção 4 da Parte 3; o que falta é processo (feature flag, janela de
  deploy), mais barato que uma vaga de engenharia da release.

---

**Resumo em uma frase:** remover o gargalo que já documentamos (FTS), colher a
feature que o design já pagou (paginação) e ganhar os olhos que o incidente
provou que faltam (observabilidade) — e aceitar, por escrito, os riscos de
tudo o que ficou de fora.
