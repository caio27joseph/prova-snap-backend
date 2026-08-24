# Parte 3 — Incidente em Produção

**Cenário:** sexta-feira, 17h30, logo após um deploy. Latência da API foi de
~200ms para 4s+, CPU do PostgreSQL em 95%, buscas em timeout, lentidão em toda
a plataforma. O deploy continha três mudanças: (1) o novo endpoint de busca,
(2) a nova funcionalidade de auditoria, (3) uma migração de banco adicionando
índices.

A resposta abaixo é escrita para **este** sistema — o backend descrito neste
repositório — não como roteiro genérico de resposta a incidentes.

---

## 1. Ações imediatas (primeiros 15 minutos)

Na ordem, porque a ordem importa:

1. **Declarar o incidente e nomear um responsável** (incident commander): uma
   pessoa coordena e comunica; as demais investigam. Sem isso, sexta 17h30
   vira cinco pessoas mexendo no banco ao mesmo tempo.
2. **Congelar deploys.** Nada mais entra em produção até entendermos o estado
   atual. O deploy das 17h30 é o principal suspeito, mas ainda não o réu.
3. **Fotografar as evidências ANTES de mexer em qualquer coisa.** Mitigar
   primeiro e investigar depois destrói exatamente o que explicaria a causa:
   - `pg_stat_activity`: o que está rodando agora, há quanto tempo, esperando o quê;
   - `pg_stat_statements` ordenado por `total_exec_time`: quem come a CPU;
   - `pg_locks` + `pg_blocking_pids()`: alguém segurando lock desde a migração?
   - contagem de conexões ativas vs. limite do pool e do Postgres;
   - salvar tudo em arquivo com timestamp — são 2 minutos de trabalho.
4. **Mitigação que não destrói evidência:** se a plataforma inteira está
   sofrendo, reduzir a pressão sem apagar o rastro — rate-limit agressivo ou
   desativação do endpoint `/api/v1/search` via configuração/proxy (as demais
   rotas da plataforma voltam a respirar enquanto investigamos). Nota honesta:
   hoje **não temos feature flag** para esse endpoint — a mitigação real seria
   no proxy/load balancer, e a ausência do flag vira item de prevenção (seção 7).
5. **Confirmar o blast radius:** é só a busca ou tudo? "Lentidão em toda a
   plataforma" + CPU do banco em 95% sugere que o banco saturado arrasta todo
   mundo — o que orienta as hipóteses abaixo.

## 2. Hipóteses iniciais (ranqueadas, amarradas às 3 mudanças do deploy)

### Hipótese 1 — o endpoint de busca: `ILIKE '%termo%'` sob tráfego real

A mais provável, porque é uma **decisão consciente do nosso design** exposta
pela primeira vez a carga de produção. A busca usa `ILIKE '%termo%'`, que faz
**seq scan por construção** — B-tree não indexa substring no meio da string.
Isso foi deliberado: busca funcional simples estava no escopo; `pg_trgm`/FTS é
a "busca otimizada" explicitamente fora dele, adiada como melhoria priorizada
(Decisão 4 do `AI_ENGINEERING_LOG.md`; `docs/ESCALABILIDADE.md`).

O detalhe que explica a CPU a 95%: nosso **LIMIT interno fixo (50,
`SEARCH_RESULT_LIMIT` em `app/config.py`) limita as linhas retornadas, não as
linhas varridas**. Cada busca lê as tabelas inteiras
independentemente de devolver poucas linhas. Um usuário com as 3 permissões
dispara 3 varreduras por requisição (uma por app). Com tráfego real de
sexta-feira — ou um termo curto/popular repetido — o banco vira uma fábrica de
seq scans concorrentes. Explica: CPU do banco, latência de 4s, timeout nas
buscas e a lentidão geral (o banco saturado penaliza todas as rotas).

### Hipótese 2 — a auditoria: escrita síncrona multiplicada + segunda sessão por requisição

A trilha de auditoria grava **1 linha por app pesquisada** (Decisão 6): uma
busca com 3 permissões gera 3 INSERTs, **síncronos, dentro do fluxo da
resposta**, numa tabela com dois índices B-tree compostos
(`user_id+timestamp`, `app+timestamp` — ver
`alembic/versions/e606788ed467_...py`). Sob pico de buscas isso significa:

- **amplificação de escrita**: cada INSERT atualiza heap + 2 índices + WAL —
  pressão de I/O e CPU que não existia antes do deploy;
- **pressão no pool de conexões**: a auditoria usa **sessão separada da
  sessão da busca** (Decisão 6 — separada para que falha de auditoria nunca
  quebre a resposta). Cada requisição pode ocupar 2 conexões simultâneas; com
  o pool default do SQLAlchemy (5 + 10 de overflow, `app/db.py`), o pool
  esgota bem antes do esperado — requisições esperando conexão explicam
  latência alta **mesmo com queries individuais rápidas**.

Sozinha, dificilmente explica 95% de CPU; combinada com a Hipótese 1, agrava.

### Hipótese 3 — a migração de índices: locks, planner e estatísticas velhas

Três mecanismos distintos:

- **Lock na criação**: `CREATE INDEX` sem `CONCURRENTLY` (o default do
  Alembic/`op.create_index`) segura lock que bloqueia escritas na tabela
  durante a construção. Numa janela de deploy de sexta com tráfego, filas de
  espera se formam — `pg_locks` responde isso em segundos.
- **Planner mudou de ideia**: índices novos mudam as escolhas do planejador.
  Um plano que era razoável pode ter virado um plano ruim (ex.: index scan +
  filtro caro em vez do seq scan que era "barato" para tabela pequena).
- **Estatísticas velhas pós-DDL**: se `ANALYZE` não rodou após a migração, o
  planner decide com estatísticas defasadas — planos ruins até o autovacuum
  passar.

Cada índice novo também adiciona custo de manutenção por escrita — que
retroalimenta a Hipótese 2 na tabela de auditoria.

## 3. Como identificar a causa raiz

Método: **medir antes de opinar**, do sintoma para a query, da query para o plano.

1. **`pg_stat_statements` ordenado por `total_exec_time`** (e por `calls`).
   Se o topo é o SELECT com `ILIKE` → Hipótese 1. Se são os INSERTs de
   auditoria em volume anormal → Hipótese 2. Se nada domina mas tudo está
   lento → olhar locks e pool (Hipóteses 2/3).
2. **`EXPLAIN (ANALYZE, BUFFERS)` na query suspeita**, com um termo real do
   tráfego. Seq scan com milhões de buffers lidos confirma a Hipótese 1;
   um plano estranho usando os índices novos confirma a variante "planner" da
   Hipótese 3. Comparar com o plano esperado pré-migração (staging tem o
   schema antigo — comparar lá).
3. **`pg_locks` + `pg_blocking_pids()` + `pg_stat_activity.wait_event`**:
   cadeia de bloqueio apontando para a sessão da migração → Hipótese 3.
4. **Conexões**: `SELECT count(*) FROM pg_stat_activity` vs. `max_connections`
   e vs. tamanho do pool da aplicação; muitas requisições em "espera por
   conexão" no lado da app → componente da Hipótese 2.
5. **`pg_stat_user_tables`**: `seq_scan` disparado nas nossas tabelas desde o
   deploy é a assinatura numérica da Hipótese 1; `last_analyze`/`last_autoanalyze`
   anteriores à migração confirmam estatísticas velhas (Hipótese 3).
6. **Linha do tempo**: correlacionar o minuto exato da degradação (logs da
   aplicação) com o minuto da migração e do primeiro tráfego no endpoint novo.
   Se a latência subiu junto com as primeiras buscas — e não durante a
   migração — a Hipótese 3 (locks) perde força.

## 4. Rollback imediato? Decisão fundamentada

**Não como reflexo — como decisão em duas partes, porque as duas metades do
deploy têm custos de reversão completamente diferentes:**

**Aplicação (endpoint de busca + auditoria): rollback é barato, rápido e
reversível.** Voltar a imagem anterior remove as duas features novas em
minutos, sem tocar em dados. **Decisão: se a mitigação da seção 1 (desativar o
endpoint no proxy) não bastar, ou não for possível, fazemos o rollback da
aplicação imediatamente — antes mesmo de conhecer a causa raiz.** Sexta 17h30,
plataforma inteira degradada: restaurar o serviço vem antes de entender o
problema, desde que a reversão não destrua dados nem evidências — e esta não
destrói (as fotografias da seção 1 já foram tiradas). As tabelas e colunas
novas podem ficar: schema aditivo é compatível com o código antigo, que as
ignora.

**Migração (índices): NÃO reverter às pressas — a reversão não é simétrica.**

- `alembic downgrade` às cegas numa sexta à noite é como se causam incidentes
  secundários: no nosso caso o `downgrade()` desta revisão **dropa as
  tabelas** (`alembic/versions/e606788ed467_...py`) — perderíamos a trilha de
  auditoria já gravada. Downgrade automático em produção está fora de questão.
- Se a investigação apontar um índice específico como culpado (variante
  "planner" da Hipótese 3), o remédio é cirúrgico: `DROP INDEX` daquele
  índice (rápido, não destrói dados) **ou** simplesmente rodar `ANALYZE`
  (se o problema for estatística velha — mais barato ainda). Decisão guiada
  pelo `EXPLAIN`, não pelo relógio.
- E se os índices não forem a causa, removê-los não ganha nada e ainda
  refaria o custo de recriá-los depois.

**Resumo da decisão:** app faz rollback cedo se preciso (barato, reversível,
preserva dados); migração só se corrige com evidência e com comando pontual,
nunca com downgrade cego.

## 5. Métricas, logs e ferramentas de apoio

**No banco (temos hoje, é onde o incidente mora):**
- `pg_stat_statements` (se a extensão não estiver habilitada, habilitar é a
  primeira prevenção da seção 7);
- `pg_stat_activity`, `pg_locks`, `pg_stat_user_tables` (contadores de
  seq scan), `pg_stat_bgwriter`/taxa de WAL para a pressão de escrita;
- log de slow queries (`log_min_duration_statement`, ex.: 500ms);
- `EXPLAIN (ANALYZE, BUFFERS)` para os planos.

**Na aplicação e no host:**
- logs da aplicação com timestamps (linha do tempo da degradação; erros de
  timeout e de pool esgotado);
- latência p95/p99 **por endpoint** — separa "a busca está lenta" de "tudo
  está lento";
- métricas de container/host: CPU, I/O e memória do Postgres e da API
  (`docker stats`, métricas do sistema).

**Honestidade sobre o nosso estado atual:** a stack ainda **não tem APM,
tracing distribuído nem dashboards** — observabilidade (OpenTelemetry) é
exatamente uma das melhorias candidatas da Parte 4. Neste incidente, a
investigação se apoiaria nas ferramentas nativas do Postgres e nos logs — que
bastam para as três hipóteses acima, mas com mais trabalho manual do que
deveria. Essa lacuna entra na prevenção.

## 6. Comunicação de status aos stakeholders

- **Reconhecimento inicial em até 15 minutos** após a detecção: "sabemos,
  estamos atuando" — mesmo sem diagnóstico. Silêncio é o que mais corrói
  confiança.
- **Cadência fixa: atualização a cada 30 minutos**, mesmo que seja "sem
  novidade, seguimos investigando X". Cadência anunciada evita a enxurrada de
  "e aí?" que consome o time.
- **Duas audiências, duas linguagens:**
  - *Stakeholders não técnicos / cliente:* impacto ("buscas indisponíveis ou
    lentas; demais funções operando com lentidão"), o que estamos fazendo, e
    previsão honesta ("próxima atualização às 18h30") — **sem jargão**: nada
    de "seq scan" ou "lock de DDL" nesse canal. Relevante no nosso contexto:
    a plataforma roda on-premises em órgãos de controle — o contato técnico
    do cliente pode precisar executar ações (ex.: acesso ao banco), então
    este canal também pede instruções claras e calmas.
  - *Time técnico:* canal dedicado do incidente com hipóteses, comandos
    executados e resultados — vira a linha do tempo do post-mortem de graça.
- **Um canal único de status por audiência** (status page ou tópico fixo);
  quem comunica é o incident commander, não cada engenheiro.
- **Encerramento explícito:** quando resolver, comunicar resolução, causa em
  uma frase e que haverá post-mortem.

## 7. Prevenção pós-resolução

Em ordem de custo-benefício:

1. **Não deployar sexta no fim do dia — ou deployar desarmado.** Janela de
   deploy com horário de fim e gente disponível; mudanças de risco atrás de
   **feature flag** (a mitigação que nos faltou na seção 1: desligar o
   endpoint novo por configuração, sem redeploy).
2. **Padrão de migração segura:** `CREATE INDEX CONCURRENTLY` para índices em
   tabelas com tráfego + `ANALYZE` explícito ao fim de toda migração de DDL +
   proibição de `downgrade()` destrutivo apontado para produção.
3. **Teste de carga do endpoint de busca antes do próximo deploy** com volume
   realista de dados: o `ILIKE '%termo%'` era um gargalo **conhecido e
   documentado** (`docs/ESCALABILIDADE.md`); o que faltou foi saber *em que
   volume* ele quebra. Isso também antecipa a promoção do `pg_trgm`/FTS na
   fila da Parte 4 — o incidente é o dado de priorização que faltava.
4. **Rate limiting no endpoint de busca e dimensionamento explícito do pool**
   de conexões (hoje, default do SQLAlchemy) considerando as 2 sessões por
   requisição do design de auditoria — ambos já são candidatos da Parte 4;
   o incidente lhes dá prioridade.
5. **Evoluir a auditoria para escrita assíncrona/enfileirada** (caminho já
   previsto em `docs/ESCALABILIDADE.md`): tira os INSERTs do caminho crítico
   da resposta e desacopla o pico de buscas do pico de escrita. Mantém o
   invariante da Decisão 6: falha de auditoria nunca quebra a busca.
6. **Observabilidade e alerta antes do usuário reclamar:** habilitar
   `pg_stat_statements` como padrão de ambiente, alertas de p95 por endpoint
   e de CPU do banco, e OpenTelemetry (Parte 4) — o incidente foi detectado
   pelo sintoma na plataforma, não por um alerta nosso.
7. **Runbook de rollback escrito** (o raciocínio da seção 4 vira documento):
   o que reverter, em que ordem, o que nunca reverter automaticamente.
8. **Post-mortem sem culpados** em até uma semana, com linha do tempo, causa
   raiz, e estas ações com dono e prazo — o objetivo é corrigir o sistema
   (processo de deploy, lacunas de teste), não achar quem errou.
