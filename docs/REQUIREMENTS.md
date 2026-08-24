# Requirements — Prova Técnica Backend Python/FastAPI (Snap Forensics)

Source: `provaBackEndStack202602-1.pdf` (received 2026-08-24).

## Logistics (hard constraints)

- **Deadline:** 7 calendar days from receipt → **deliver by 2026-08-31** (aim for 2026-08-30 to leave buffer).
- **Estimated effort:** 6–8 hours.
- **Delivery:**
  - **Private** repo on GitHub/GitLab.
  - Add `guilherme.rabelo@snapforensics.com` as collaborator.
  - On completion, send email with subject **"Prova Técnica – [Seu Nome]"** to that address **and** the HR contact following the process.

## What is evaluated (grading rubric)

1. **Raciocínio técnico** — justify architectural decisions.
2. **Experiência prática** — show real-world problem experience.
3. **Pragmatismo** — simple, effective solutions.
4. **Documentação clara** — a non-technical client must understand.
5. **Tratamento de erros** — robust scripts, not just the happy path.

Additional notes from the exam:
- AI-First environment: AI usage is allowed and **encouraged**, but all technical decisions/validations/final deliverables must reflect **your own engineering judgment**.
- Comment **non-obvious decisions** in code.
- If blocked, **document what you tried** — it counts for points.

## Explicitly OUT of scope (do NOT build)

- Real Keycloak setup (mocking JWT is fine).
- Full CI/CD (describing it is sufficient).
- Frontend.
- Optimized search (basic functional search is OK).

## Project context

Investigative intelligence platform, distributed **on-premises**, for control agencies, corporate compliance, and financial investigations. 3 main applications:

1. **Analytics** — analytical reports, dashboards, exports.
2. **Investigator** — relationship graphs, timeline, link analysis.
3. **Case Manager** — investigative case management, task assignment, workflow.

---

## PARTE 1 — Multi-Application Authentication Architecture (written)

SSO scenario requirements:
- User logs in **once**, accesses all permitted apps.
- Each app controls **its own permissions** independently.
- Removing access to one app does **not** affect the others.
- Audit: know **which app** the user accessed and **when**.

### 1.1 Decisão Fundamentada — choose Option A or B
- **Option A:** single Keycloak realm `platforma` with clients `analytics-api`, `investigator-api`, `case-manager-api`.
- **Option B:** multiple realms (`analytics`, `investigator`, `case-manager`).

Must explain:
- Which option and **why**.
- Trade-offs of each (complexity vs isolation vs UX).
- How to implement SSO in the chosen option.
- How to manage independent permissions per app.

### 1.2 Modelo de Permissionamento (text/diagram allowed)
Example user: João Silva → Analytics role `viewer` (sees own reports), Investigator role `senior-investigator` (full access), Case Manager: NO ACCESS.

Answer:
- How to store these permissions?
- How does the API validate user access to endpoint X?
- How to make the JWT carry **only relevant permissions**?
- How to implement per-application access auditing?

### 1.3 Análise de Cenários
- **Cenário 1:** Admin must grant Analytics access to 50 new users while 300 existing users have Investigator access — how, without affecting existing users?
- **Cenário 2:** Investigator calls an Analytics endpoint internally (API-to-API). How to authenticate? Service account? Reuse the user's JWT?

---

## PARTE 2 — Multi-Application Search Endpoint (code)

One shared endpoint `POST/GET /api/v1/search` used by all 3 apps, behaving differently by **origin app** and **user permissions**:

- Know which application the request came from.
- Validate the user has permission for that specific application.
- Search only data relevant to that application.
- Return appropriately formatted results.
- Log the search for audit.

### Tables
- `analytics_reports (id, title, content, created_at)`
- `investigator_entities (id, type, name, data, created_at)`
- `case_manager_cases (id, title, assigned_to, status, created_at)`
- `search_audit_log (id, user_id, app, query, timestamp)`

### Per-app search rules
| App | Required permission | Searches | Returns |
|---|---|---|---|
| Analytics | `analytics:search` | content of generated reports only | aggregated data (no sensitive detail) |
| Investigator | `investigator:search` | entities of types: pessoas, empresas, transações, documentos | full data |
| Case Manager | `case-manager:search` | only cases **assigned to the user** | metadata only (no content search) |

### Deliverables
1. **Models** for the tables above.
2. **Alembic migration** with the tables, **necessary indexes**, and **seed data (10 rows for each of the first 3 tables)**.
3. **Endpoint** with FastAPI routes enforcing required permissions, per-app contextual search logic, **result aggregation when the user holds multiple permissions**, and audit logging.
4. **Tests (pytest)** — at least 5:
   - User with `analytics:search` gets only Analytics data.
   - User with `investigator:search` gets Investigator data.
   - User with both permissions gets **aggregated** results.
   - User without permission gets **HTTP 403**.
   - Search is recorded in the **audit log**.
5. **JWT Authentication**
   - Implement as a FastAPI dependency.
   - Extract: `user_id`, `app_client_id`, `permissions`.
   - Keycloak may be mocked (`python-jose` or another lib).
   - **Document the expected JWT structure.**

---

## PARTE 3 — Production Incident (written)

Friday 17:30, post-deploy: API latency 200ms → 4s+, PostgreSQL CPU at 95%, searches timing out, platform-wide slowness. Deploy contained: new search endpoint, new audit feature, new DB migration adding indexes.

Answer at minimum:
- Immediate actions.
- Initial hypotheses.
- How to identify the root cause.
- Roll back immediately? Why / why not?
- Metrics, logs, tools used to support the investigation.
- Incident status communication to stakeholders.
- Post-resolution preventive actions.

---

## PARTE 4 — Engineering Trade-offs Review (written)

Team capacity for only **3 improvements** next release, from: pagination, rate limiting, Redis cache, OpenTelemetry observability, more automated tests, CI pipeline with automatic validations, more granular permission model, full-text search, relevance/ranking, improved deploy rollback strategy.

Answer:
- Which 3 and why.
- Execution order.
- Prioritization criteria.
- Which risks are acceptable to assume now.

---

## PARTE 5 — AI Usage Report (`AI_ENGINEERING_LOG.md`, required file)

1. **Tools used** — list them.
2. **Where AI helped** — up to 3 situations: the problem, how AI helped, the result.
3. **Where AI was wrong** — at least 1 case: what was suggested, why it was problematic, how you detected it, what you did instead.
4. **Engineering decisions** — at least 2 important decisions: alternatives considered, decision taken, why.
5. **AI interaction examples** (optional) — up to 3 relevant interactions.

> ⚠️ Maintain this log **continuously during development**, not retroactively at the end.

---

## Proposed repository layout

```
prova-snap-backend/
├── README.md                 # setup, run, decisions overview (client-readable)
├── AI_ENGINEERING_LOG.md     # Parte 5 (living document)
├── docs/
│   ├── REQUIREMENTS.md       # this file (internal)
│   ├── PARTE1_AUTH.md        # SSO architecture answers
│   ├── PARTE3_INCIDENT.md    # incident response answers
│   ├── PARTE4_TRADEOFFS.md   # prioritization answers
│   └── JWT_STRUCTURE.md      # documented expected JWT
├── app/
│   ├── main.py
│   ├── config.py
│   ├── auth/                 # JWT dependency, permission checks
│   ├── models/               # SQLAlchemy models
│   ├── schemas/              # Pydantic schemas
│   ├── services/             # per-app search strategies + aggregation + audit
│   └── api/                  # /api/v1/search router
├── alembic/                  # migration + seed
├── tests/                    # pytest (≥5 required cases + edge cases)
├── docker-compose.yml        # PostgreSQL (nice-to-have for evaluator DX)
├── pyproject.toml
└── .env.example
```

## Definition of Done checklist

- [ ] Parte 1 answered (decision + trade-offs + SSO + permissions + 2 scenarios)
- [ ] Models for the 4 tables
- [ ] Alembic migration with indexes + seed (10×3 tables)
- [ ] `/api/v1/search` with permission enforcement, per-app logic, aggregation, audit
- [ ] JWT dependency extracting `user_id`, `app_client_id`, `permissions` (mocked Keycloak)
- [ ] JWT structure documented
- [ ] ≥5 pytest tests covering the 5 mandated cases — all green
- [ ] Parte 3 incident write-up
- [ ] Parte 4 trade-offs write-up
- [ ] `AI_ENGINEERING_LOG.md` complete (tools, 3 wins, ≥1 AI failure, ≥2 decisions)
- [ ] README a non-technical client can follow
- [ ] Error handling beyond the happy path (invalid token, expired token, empty query, unknown app, DB down)
- [ ] Non-obvious decisions commented in code
- [ ] Private repo + collaborator `guilherme.rabelo@snapforensics.com` added
- [ ] Email sent: "Prova Técnica – Caio Joseph A. Silveira"
