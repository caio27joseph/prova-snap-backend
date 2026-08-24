# Dev shortcuts — the canonical requirements live in docs/DEVELOPMENT.md.
.PHONY: up down dev test lint fmt check

up:            ## start Postgres (dev + test DBs) and wait until healthy
	docker compose up -d
	@timeout 60 bash -c 'until docker compose ps postgres --format "{{.Health}}" | grep -q healthy; do sleep 2; done'
	@echo "postgres healthy"

down:          ## stop Postgres (data volume is kept)
	docker compose down

dev: up        ## run the API with hot reload
	uv run uvicorn app.main:app --reload

test: up       ## run the test suite (real Postgres, see docs/TEST_STRATEGY.md)
	uv run pytest

lint:          ## static checks (ruff)
	uv run ruff check .

fmt:           ## auto-format + autofix
	uv run ruff format . && uv run ruff check --fix .

check: lint test   ## everything that must be green before a merge
