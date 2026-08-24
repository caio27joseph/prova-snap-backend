"""add pg_trgm gin indexes for text search

Parte 4 improvement nº 1 (docs/PARTE4_TRADEOFFS.md §1.1, ticket T-11): GIN
trigram indexes on the three columns the search strategies ILIKE against —
analytics_reports.content, investigator_entities.name, case_manager_cases.title.

Zero contract change is the whole point: ILIKE '%termo%' with escape — exactly
what the strategies emit today — is exactly the pattern gin_trgm_ops
accelerates. The application code does not know the index exists; the
strategies in app/services/search/ are untouched.

Safe-migration standard (docs/PARTE3_INCIDENT.md, prevenção nº 2): indexes are
created with CREATE INDEX CONCURRENTLY and the migration ends with an explicit
ANALYZE. In dev these tables hold 10 rows and plain CREATE INDEX would be
instant — but this migration is the production-safe pattern our own incident
doc mandates, so it models it.

Revision ID: 82d0b9d6d764
Revises: e606788ed467
Create Date: 2026-08-24 17:56:01.778820

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "82d0b9d6d764"
down_revision: str | Sequence[str] | None = "e606788ed467"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (index name, table, column) — names mirrored in the models' __table_args__
# so `alembic check` stays drift-free (same convention as the T-03 indexes).
TRIGRAM_INDEXES = [
    ("ix_analytics_reports_content_trgm", "analytics_reports", "content"),
    ("ix_investigator_entities_name_trgm", "investigator_entities", "name"),
    ("ix_case_manager_cases_title_trgm", "case_manager_cases", "title"),
]


def upgrade() -> None:
    # Requires superuser or an extension whitelist (e.g. RDS); the compose
    # stack's POSTGRES_USER is superuser in the official image — verified.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # CONCURRENTLY cannot run inside a transaction, hence the autocommit block.
    # It is the PARTE3 prevention-nº 2 standard for tables with traffic: plain
    # CREATE INDEX holds a lock that blocks writes for the whole build.
    with op.get_context().autocommit_block():
        for name, table, column in TRIGRAM_INDEXES:
            op.create_index(
                name,
                table,
                [column],
                postgresql_using="gin",
                postgresql_ops={column: "gin_trgm_ops"},
                postgresql_concurrently=True,
            )

    # Same prevention standard: explicit ANALYZE after DDL, so the planner
    # doesn't run on stale statistics until autovacuum happens to pass by.
    for _, table, _ in TRIGRAM_INDEXES:
        op.execute(f"ANALYZE {table}")


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for name, table, _ in TRIGRAM_INDEXES:
            op.drop_index(name, table_name=table, postgresql_concurrently=True)
    # The extension is deliberately NOT dropped: other objects may depend on it
    # by now, and destructive downgrades are the exact anti-pattern
    # docs/PARTE3_INCIDENT.md (seção 4) warns against. Leaving pg_trgm
    # installed is harmless; DROP EXTENSION could not be.
