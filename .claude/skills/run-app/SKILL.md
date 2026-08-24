---
name: run-app
description: Launch and smoke-test this FastAPI app (docker compose Postgres + uvicorn). Use when asked to run, start, verify, or debug the app or the dev environment.
---

# Running this app (verified 2026-08-24)

Stack: FastAPI + sync SQLAlchemy + PostgreSQL via docker compose. The API runs
locally with uvicorn; only the database is containerized.

## Launch

```bash
docker compose up -d
# wait until healthy (healthcheck: pg_isready, ~5s)
timeout 60 bash -c 'until docker compose ps postgres --format "{{.Health}}" | grep -q healthy; do sleep 2; done'

uv sync                                   # first time only
uv run uvicorn app.main:app --port 8000   # add --reload for human dev sessions
```

For agent use, launch uvicorn in the background and kill it when done — do not
leave servers running across turns.

## Smoke test (drive it, don't just launch)

```bash
curl -s localhost:8000/health
# expect: {"status":"ok","database":"up"}  [200]
# with DB stopped: {"status":"degraded","database":"down"}  [503] — this is the
# controlled-error contract, a stacktrace here is a bug
```

Swagger UI: http://localhost:8000/docs — lists every implemented route.
`/api/v1/search` requires a Bearer JWT (mocked Keycloak, HS256); mint test
tokens with the helper documented in docs/JWT_STRUCTURE.md once implemented.

## Known gotchas (already solved, don't rediscover)

- **Port 5432 taken on this machine** (another project's Postgres). The compose
  host port is parameterized: local `.env` (gitignored) sets `POSTGRES_PORT=5433`
  and `DATABASE_URL=postgresql+psycopg://prova:prova@localhost:5433/prova`.
  Do NOT stop other containers to free 5432.
- **Test database**: `prova_test` is created by `docker/init-test-db.sql` only
  on first init of an empty volume. If it's missing (old volume), conftest
  recreates it — or manually:
  `docker compose exec postgres psql -U prova -c 'CREATE DATABASE prova_test OWNER prova'`.
- **Tests need the compose Postgres up** (`pytest` fails fast with a clear
  message otherwise — by design, see docs/TEST_STRATEGY.md).
