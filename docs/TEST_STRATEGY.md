# Estratégia de Testes

Define como a suíte de testes prova que a Parte 2 funciona — incluindo os 5 testes
obrigatórios do enunciado e os caminhos de erro que a rubrica valoriza
("tratamento de erros: robusto, não só o caminho feliz").

## Stack

- **pytest** como runner.
- **httpx** (`ASGITransport`/TestClient) para exercitar a API de ponta a ponta,
  sem servidor externo.
- **PostgreSQL real via Docker** como banco de testes (decisão abaixo).

## Decisão: Postgres com fixture Docker (não SQLite)

**Alternativas consideradas:**

| Opção | Prós | Contras |
|---|---|---|
| SQLite in-memory | Zero dependência, `pytest` roda após clone, rápido | Não é o engine de produção: `ILIKE`, JSONB e comportamento de índices divergem; testes provariam um banco que não existe em prod |
| **Postgres via Docker (escolhida)** | Paridade total com produção; a migration Alembic (com índices) é testada de verdade; queries usam o dialeto real | Exige Docker rodando para testar; fixtures um pouco mais lentas |
| Híbrido (SQLite default + Postgres opt-in) | Melhor dos dois | Complexidade de conftest difícil de justificar numa prova de 6–8h |

**Por que Postgres:** o deliverable inclui migration com índices e busca textual —
exatamente as áreas onde SQLite diverge do Postgres. Testes que passam em SQLite
e falham em Postgres seriam pior que inexistentes. O custo (Docker como
pré-requisito) já existe no projeto: o docker-compose de dev é entregável de
qualquer forma, e o README documenta o passo único `docker compose up -d`.

> Registrado também em `AI_ENGINEERING_LOG.md` (Decisão 3): a IA recomendou
> SQLite priorizando a conveniência do avaliador; a recomendação foi rejeitada
> em favor da paridade com produção.

## Arquitetura das fixtures

- **Banco de teste separado** (`prova_test`) na mesma instância Postgres do
  docker-compose — testes nunca tocam o banco de dev/seed.
- **Escopo de sessão:** engine criado uma vez; **migrations Alembic aplicadas no
  início da sessão de teste** (isso valida a migration como parte da suíte, em
  vez de usar `create_all`, que poderia divergir dela).
- **Escopo de função:** cada teste roda dentro de uma transação com **rollback ao
  final** — isolamento total entre testes sem custo de recriar o schema.
- **Dados de teste explícitos por teste** (factories/fixtures pequenas) para
  testes de *feature* — cada teste declara o que espera encontrar. Exceção
  deliberada: os testes de **migração** (T-03) asseram contra o seed, porque o
  seed é o próprio artefato sob teste; o seed é determinístico (UUIDs e datas
  hardcoded), então essas asserções são estáveis.
- **JWTs forjados por um helper** (`make_token(user_id, app, permissions, exp)`),
  assinados com o mesmo segredo HS256 de teste — cobre tokens válidos, expirados,
  malformados e com claims ausentes.

## Matriz de testes

### Obrigatórios pelo enunciado (mínimo 5)

| # | Cenário | Verificação |
|---|---|---|
| 1 | Usuário com `analytics:search` | Recebe **apenas** dados de Analytics, agregados, sem detalhe sensível |
| 2 | Usuário com `investigator:search` | Recebe dados de Investigator (dados completos) |
| 3 | Usuário com ambas as permissões | Resposta **agregada** das duas fontes |
| 4 | Usuário sem permissão | **HTTP 403** |
| 5 | Busca bem-sucedida | Linha gravada em `search_audit_log` (user_id, app, query, timestamp) |

### Regras por app (além do mínimo)

- Case Manager retorna **somente casos atribuídos ao usuário** (caso de outro
  usuário não aparece) e **somente metadados** (sem busca em conteúdo).
- Investigator busca apenas os tipos permitidos de entidade
  (pessoas, empresas, transações, documentos).

### Caminhos de erro (rubrica de robustez)

| Cenário | Esperado |
|---|---|
| Sem header `Authorization` | 401 |
| Token malformado (não é JWT) | 401 |
| Assinatura inválida | 401 |
| Token expirado | 401 |
| Claims obrigatórios ausentes (`sub`, `azp`, permissions) | 401 |
| Token válido, mas nenhuma permissão `<app>:search` | 403 |
| Usuário com permissão de 1 app não recebe dados dos outros | resposta contém só o app permitido |
| Query vazia | 422 |
| Query acima do limite de tamanho | 422 |
| App de origem desconhecido (`azp` fora dos 3 clients) | 401 — azp faz parte da confiança no token (Decisão 9 do AI log) |
| Banco indisponível | 503 com corpo de erro controlado (nunca stacktrace) |
| **Falha no audit log não derruba a busca** | Busca responde 200; falha de audit é logada, não propagada |

O último caso é o inverso do teste obrigatório nº 5: juntos eles provam a regra
"audit nunca quebra a resposta, mas é sempre gravado quando possível".

## Escopo e forma dos testes

- **Integração via API é o padrão:** o entregável é o endpoint; testes que passam
  pelo HTTP + dependency de auth + service + banco real são a evidência mais
  barata e mais fiel. Unit tests só onde houver lógica pura que mereça
  (ex.: parsing de claims), sem duplicar o que a integração já cobre.
- **Um comportamento por teste**, nome descritivo em inglês no padrão
  `test_<cenario>_<resultado>` (ex.: `test_search_without_permission_returns_403`).
- Sem meta de cobertura numérica: a meta é **matriz acima 100% implementada**.
  Cobertura percentual seria proxy fraco numa prova curta.

## Como rodar

```bash
docker compose up -d          # sobe o Postgres (dev + test DB)
pytest                        # roda a suíte completa
```

O `conftest.py` cria o banco `prova_test` se não existir e falha com mensagem
clara ("Postgres não acessível — rode `docker compose up -d`") se o Docker não
estiver de pé, em vez de um erro críptico de conexão.
