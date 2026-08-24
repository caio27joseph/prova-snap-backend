---
name: worktree-new
description: Start a new work block (Parte branch) in an isolated git worktree for parallel work on this machine. Use when asked to open/start a branch, begin a Parte block, or work on something in parallel.
---

# Starting a work block in a worktree

Branch names come from the planned table in docs/COMMIT_STRATEGY.md
(`parte1-auth-design`, `parte2-models-migrations`, `parte2-auth`,
`parte2-search`, `parte2-error-paths`, `parte3-incident`, `parte4-tradeoffs`).

```bash
scripts/wt.sh new <branch>        # creates ../prova-snap-backend.wt/<branch>
cd ../prova-snap-backend.wt/<branch>
```

The script bootstraps everything: branch off `main`, copies the machine-local
`.env` (port overrides — without it the app targets the wrong Postgres port),
and runs `uv sync`.

## Rules while inside a worktree

- **Never `docker compose up` here.** One shared Postgres stack, managed from
  the primary checkout, serves every worktree.
- **Pick a unique uvicorn port** per worktree (`--port 8001`, `8002`, ...) so
  parallel apps don't collide.
- **Test runs are serial across worktrees** until conftest honors
  `TEST_DATABASE_URL` (planned for parte2) — two suites sharing `prova_test`
  would corrupt each other's fixtures.
- Commits follow CLAUDE.md: propose and get explicit approval first.
