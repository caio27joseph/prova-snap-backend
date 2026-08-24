# Backlog — tickets por bloco de trabalho

Um ticket por branch planejada ([COMMIT_STRATEGY](COMMIT_STRATEGY.md)). Status
atualizado a cada merge. Estimativas somam ~8h30 (orçamento do enunciado: 6–8h
— o excedente já foi pago na fase de setup/decisões).

**DoD comum a todos os tickets** (além dos critérios específicos):
`make check` verde · decisões novas registradas no `AI_ENGINEERING_LOG.md` no
mesmo commit · docs afetados atualizados · merge `--no-ff` aprovado pelo Caio.

---

## T-01 · Setup e fundações — ✅ CONCLUÍDO (merge `f328618` + commits em main)

Scaffold, docker-compose, health, estratégias, worktrees, Makefile, README,
11 decisões de arquitetura registradas.

---

## T-02 · Parte 1: resposta escrita de autenticação — ✅ CONCLUÍDO (branch `parte1-auth-design`)

**Objetivo:** completar `docs/PARTE1_AUTH.md` (1.2 e 1.3) e criar
`docs/JWT_STRUCTURE.md`.

**Critérios de aceitação:**
- [x] 1.2 responde as 4 perguntas (armazenamento, validação na API, JWT
      enxuto, auditoria por app) usando as Decisões 2, 6 e 9 — incluindo a
      pegadinha do ownership (viewer vê relatórios *do João*) sem vazar
      escopo para o schema da Parte 2.
- [x] 1.3 Cenário 1: onboarding de 50 usuários via grupo + client role, sem
      tocar nos 300 existentes.
- [x] 1.3 Cenário 2: posição fundamentada service account vs JWT do usuário,
      com propagação de identidade para auditoria.
- [x] `JWT_STRUCTURE.md`: exemplo completo de token (header/payload), claims
      obrigatórios, tabela de usuários de teste (UUIDs fixos), taxonomia
      401/403.
- [x] Extra: `app/auth/mock_users.py` (contrato de identidade) + 20 testes
      pytest guardando os invariantes das personas.

**DoD específico:** pt-BR, sem jargão não explicado; todo argumento
não-óbvio cita fonte ou decisão do log. **Estimativa:** 1h15.

---

## T-03 · Parte 2: models + migração + seed — ✅ CONCLUÍDO (branch `parte2-models-migrations`)

**Objetivo:** 4 models SQLAlchemy tipados + migração Alembic única com
índices e seed.

**Critérios de aceitação:**
- [ ] Models com PK UUIDv7 (app-side), `timestamptz` + `server_default`,
      `data` como JSONB; audit com colunas estendidas (Decisão 6) e
      `app`/`results_count` anuláveis (linha de negado).
- [ ] Migração cria tabelas + índices B-tree das colunas de filtro (Decisão
      4), cada índice com comentário do porquê.
- [ ] Seed na migração: 10×3 registros pt-BR determinísticos (UUIDs
      hardcoded), incluindo ≥1 entidade de tipo NÃO buscável e casos
      atribuídos aos usuários de teste do T-02.
- [ ] `alembic upgrade head` roda limpo em banco zerado (provado no fresh
      volume); conftest inicial aplica migrações no banco de teste e honra
      `TEST_DATABASE_URL` (destrava worktrees paralelos).

**Depende de:** T-02 (UUIDs dos usuários de teste). **Estimativa:** 1h30.

---

## T-04 · Parte 2: autenticação JWT — ✅ CONCLUÍDO (branch `parte2-auth`)

**Objetivo:** dependency FastAPI que valida o token mock e produz
`AuthContext(user_id, app_client_id/origin_app, permissions)`.

**Critérios de aceitação:**
- [ ] PyJWT HS256; validação estrita: assinatura, `exp`, claims obrigatórios
      (`sub`, `azp`, `resource_access`), `azp` ∈ KNOWN_CLIENTS.
- [ ] Normalização `resource_access.<client>.roles` → `<app>:<role>` (único
      formato aceito — Decisão 2).
- [ ] Taxonomia 401/403 da Decisão 9 implementada e testada: sem header,
      malformado, assinatura inválida, expirado, claims ausentes, azp
      desconhecido → 401; zero permissões de busca → 403.
- [ ] Helper de teste `make_token(...)` cobrindo todos os casos acima.

**Depende de:** T-03 (conftest). **Estimativa:** 1h.

---

## T-05 · Parte 2: endpoint de busca — ✅ CONCLUÍDO (branch `parte2-search`)

**Objetivo:** `POST /api/v1/search` completo: strategies por app, agregação,
auditoria, response models.

**Critérios de aceitação:**
- [ ] Strategy por app atrás de um service; Analytics busca só `content` e
      retorna `total_matched` + `by_month`; Investigator busca `name` dos 4
      tipos e retorna dados completos; CaseManager busca `title` só de casos
      `assigned_to = sub` e retorna metadados.
- [ ] Escopo = todas as apps permitidas; resposta agrupada por app com
      envelope cursor-ready; LIMIT interno 50; `escape_like` aplicado.
- [ ] Auditoria: 1 linha por app pesquisada (status `ok`) e linha única de
      negado no 403; falha de audit não quebra a resposta.
- [ ] Os 5 testes obrigatórios do enunciado verdes + regras por app
      (caso de outro usuário não aparece; tipo não buscável não aparece;
      teste de vazamento: nenhum título/conteúdo na seção analytics).

**Depende de:** T-04. **Estimativa:** 2h.

---

## T-06 · Parte 2: caminhos de erro — ✅ CONCLUÍDO (branch `parte2-error-paths`)

**Objetivo:** fechar 100% da matriz do [TEST_STRATEGY](TEST_STRATEGY.md).

**Critérios de aceitação:**
- [ ] Query vazia/curta/gigante → 422 (bounds 2–200, Pydantic).
- [ ] Banco indisponível → 503 com corpo controlado (handler global).
- [ ] Falha de audit → 200 + erro logado (teste com audit quebrado via mock).
- [ ] Teste `escape_like`: buscar `100%` não casa com `1000`.
- [ ] Matriz do TEST_STRATEGY 100% implementada (conferência linha a linha).

**Depende de:** T-05. **Estimativa:** 1h.

---

## T-07 · Parte 3: incidente em produção — ✅ CONCLUÍDO (branch `parte3-incident`)

**Objetivo:** `docs/PARTE3_INCIDENT.md` respondendo os 7 pontos do enunciado.

**Critérios de aceitação:**
- [ ] Ações imediatas, hipóteses (ligar os sintomas às 3 mudanças do deploy),
      método de root cause, decisão fundamentada sobre rollback, métricas/
      ferramentas, comunicação a stakeholders, prevenção.
- [ ] Amarrado ao NOSSO sistema (endpoint de busca, audit, migração de
      índices) — não um texto genérico de incident response.

**Estimativa:** 45min. Pode rodar em paralelo com T-03..T-06 (worktree).

---

## T-08 · Parte 4: trade-offs — ✅ CONCLUÍDO (branch `parte4-tradeoffs`)

**Objetivo:** `docs/PARTE4_TRADEOFFS.md` — 3 melhorias, ordem, critérios,
riscos aceitos.

**Critérios de aceitação:**
- [ ] Escolha cita dores reais do código entregue (LIMIT fixo → paginação
      cursor-ready; ILIKE seq scan → FTS; etc.).
- [ ] Ordem de execução + critérios de priorização explícitos + riscos
      aceitos nomeados.

**Depende de:** T-05 (decidir com o código na mesa — Decisão da conversa).
**Estimativa:** 45min.

---

## T-09 · Entrega — direto na `main`

**Critérios de aceitação:**
- [ ] README final (remover seção "Estado atual"); log de IA revisado
      (casos 2 e 3 da seção 2 preenchidos; interações opcionais).
- [ ] Checklist completo do [REQUIREMENTS](REQUIREMENTS.md) conferido.
- [ ] Repo privado no GitHub/GitLab + colaborador
      `guilherme.rabelo@snapforensics.com`.
- [ ] E-mail "Prova Técnica – Caio Joseph A. Silveira" enviado (com RH em
      cópia). **Prazo: 2026-08-30.**

**Depende de:** todos. **Estimativa:** 30min.

---

# Pós-entrega (após a tag `entrega-prova`)

Execução do roadmap da própria Parte 4, na ordem lá justificada, mais a CI
descrita. Trabalho claramente separado da submissão pela tag.

## T-10 · CI com GitHub Actions — branch `melhoria-ci`
`make lint` + suíte completa contra Postgres de serviço em todo push/PR.
Atualizar a seção "deliberadamente fora" do DEVELOPMENT.md (a exclusão era
da prova, não do projeto). **AC:** workflow verde no GitHub; docs coerentes.

## T-11 · Busca full-text (`pg_trgm`) — branch `melhoria-fts`
Melhoria nº 1 da Parte 4: extensão + índices GIN trigram em
`analytics_reports.content`, `investigator_entities.name`,
`case_manager_cases.title`, via `CREATE INDEX CONCURRENTLY` (padrão do
PARTE3_INCIDENT, prevenção nº 2) em nova revisão Alembic. Zero mudança de
contrato — o ILIKE existente passa a ser servido por índice. **AC:** migração
aplica limpa (upgrade + downgrade); índices provados existentes; suíte verde.

## T-12 · Paginação por cursor — branch `melhoria-paginacao`
Melhoria nº 2: aceitar `cursor` por seção no body, devolver `next_cursor`
real (id do último item). Analytics não pagina. **AC:** teste de travessia
completa sem pular/repetir item sob inserção concorrente.

## T-13 · OpenTelemetry + Grafana — branch `melhoria-otel`
Melhoria nº 3: instrumentação FastAPI+SQLAlchemy, Prometheus + Grafana no
compose (profile `observability`), 1 dashboard com os painéis do
PARTE3_INCIDENT (p95/p99 por endpoint, CPU do banco, falhas de auditoria
como métrica). **AC:** dashboard renderiza com tráfego real do smoke test.

## T-14 · Fluxo de PRs + CodeRabbit — decisão futura
Só faz sentido ao migrar merges locais para PRs no GitHub; reavaliar após
T-10 consolidar a CI.
