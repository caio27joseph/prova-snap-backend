from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Dev defaults mirror docker-compose.yml so `uvicorn app.main:app` works
    right after `docker compose up -d`, with no .env required (evaluator DX)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://prova:prova@localhost:5432/prova"
    # ≥32 bytes: RFC 7518 minimum key size for HS256 — PyJWT warns below it
    # (flagged during T-04 review; dev-only value, real deployments override).
    jwt_secret: str = "dev-secret-change-me-0123456789abcdef"
    jwt_algorithm: str = "HS256"


# Known Keycloak clients of realm "plataforma" mapped to their app identifier
# (the `<app>` half of `<app>:search` permissions and of audit rows).
# A token whose azp is not in this mapping is untrusted -> 401 (AI log, Decisão 9).
KNOWN_CLIENTS: dict[str, str] = {
    "analytics-api": "analytics",
    "investigator-api": "investigator",
    "case-manager-api": "case-manager",
}

# Resource guard: no search returns unbounded tables. Also the hard ceiling for
# the per-request `limit` since cursor pagination landed (T-12) — callers may
# page smaller, never larger (docs/ESCALABILIDADE.md).
SEARCH_RESULT_LIMIT = 50

# Query bounds enforced by the request model: 1 char can't express intent and
# would match nearly everything; 200 is generous for human search input.
QUERY_MIN_LENGTH = 2
QUERY_MAX_LENGTH = 200

settings = Settings()
