# CLAUDE.md — AI Guidelines for this Technical Test

This repo is my submission for the Snap Forensics Backend Python/FastAPI technical test.
Full spec: [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md). Deadline: **2026-08-31** (deliver by 08-30).

## Prime directive

The exam is AI-First: AI use is encouraged, but **every technical decision, validation,
and final deliverable must reflect the candidate's own engineering judgment**. Therefore:

- **Propose, don't decide.** For any architectural choice (realm strategy, permission
  model, aggregation shape, index design), present options with trade-offs and let me
  (Caio) pick. Never silently commit to a non-obvious decision.
- **Log as we go.** Every meaningful AI interaction — especially wrong or incomplete
  suggestions — gets an entry in `AI_ENGINEERING_LOG.md` immediately. Parte 5 requires
  at least 1 documented AI mistake and 2 engineering decisions; these cannot be
  reconstructed honestly at the end.
- **Flag AI failure moments.** If you correct yourself, hallucinate an API, or I reject
  your suggestion, say so explicitly — that's log material worth points.

## What the graders reward (optimize for this)

1. **Justified decisions** — every non-obvious choice gets a short "why" comment in code
   or a paragraph in docs. No unexplained magic.
2. **Real-world pragmatism** — simple > clever. No speculative abstractions, no
   unrequested features. Basic functional search is explicitly enough.
3. **Docs a non-technical client can read** — README in plain language: what it is,
   how to run it, what each part does. Avoid jargon in the README; keep depth in docs/.
4. **Error handling beyond happy path** — invalid/expired/malformed JWT, missing
   permission (403), empty/oversized query, unknown app, DB unavailable. Tests should
   cover failures, not just success.

## Scope guardrails

Do NOT build (explicitly out of scope): real Keycloak, full CI/CD (describe only),
any frontend, optimized/ranked search. If tempted, write it in Parte 4 as a
prioritized improvement instead.

## Stack decisions (fixed unless revisited deliberately)

- Python 3.12+, FastAPI, SQLAlchemy 2.x (typed, `Mapped[]`), Alembic, Pydantic v2.
- PostgreSQL via docker-compose for dev; tests may use SQLite or a Postgres fixture —
  decide and record in the log.
- JWT: `PyJWT` (deliberate revisit from `python-jose` — see log Decisão 10; the exam
  cites python-jose only as an example, "ou outra!"), HS256 mock of Keycloak token;
  expected structure documented in
  `docs/JWT_STRUCTURE.md` and mirroring real Keycloak claims
  (`sub`, `azp`, `resource_access.<client>.roles` or a flat `permissions` claim — decision to log).
- `pytest` + `httpx` TestClient. Minimum 5 mandated tests, plus error-path tests.

## Code conventions

- Comment **non-obvious decisions only** (the exam asks for exactly this); no
  narration comments, no "what the next line does".
- Per-app search logic as a strategy per application (Analytics/Investigator/CaseManager)
  behind one service — keeps the shared endpoint thin and each rule set isolated.
- Audit logging must never break the search response (log failures are caught and
  reported, not raised to the user) — but tests must prove the audit row is written
  on success.
- Keep commits small and descriptive; the repo history is part of the evaluation story.

## Language

- Code, identifiers, commit messages: **English**.
- README and written answers (Partes 1, 3, 4): **Portuguese (pt-BR)** — the evaluator
  and the "non-technical client" are Brazilian. `AI_ENGINEERING_LOG.md` in pt-BR too.

## Definition of Done

Use the checklist at the bottom of [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md).
A part is done only when its tests pass and its documentation exists.
