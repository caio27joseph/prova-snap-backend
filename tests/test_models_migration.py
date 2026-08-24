"""Proves the Alembic migration delivered what T-03 promises: schema shape,
constraints, and the deterministic seed the later search tests build on.
Extended by T-11 with the pg_trgm GIN indexes (existence + usability)."""

import uuid

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.auth.mock_users import ANA, CARLOS, OUTRO
from app.models import AnalyticsReport, CaseManagerCase, InvestigatorEntity, SearchAuditLog
from app.services.search.text import LIKE_ESCAPE_CHAR, like_pattern

SEARCHABLE_TYPES = {"pessoa", "empresa", "transacao", "documento"}

# T-11: trigram GIN indexes serving the strategies' ILIKE, one per text column.
TRIGRAM_INDEXES = {
    "ix_analytics_reports_content_trgm": "analytics_reports",
    "ix_investigator_entities_name_trgm": "investigator_entities",
    "ix_case_manager_cases_title_trgm": "case_manager_cases",
}


def _count(db_session, model, *where):
    return db_session.scalar(select(func.count()).select_from(model).where(*where))


@pytest.mark.parametrize("model", [AnalyticsReport, InvestigatorEntity, CaseManagerCase])
def test_seed_inserts_exactly_ten_rows(db_session, model):
    assert _count(db_session, model) == 10


def test_investigator_seed_contains_nonsearchable_veiculo_type(db_session):
    assert _count(db_session, InvestigatorEntity, InvestigatorEntity.type == "veiculo") >= 1


def test_investigator_seed_covers_all_searchable_types(db_session):
    seeded_types = set(db_session.scalars(select(InvestigatorEntity.type).distinct()))
    assert SEARCHABLE_TYPES <= seeded_types


def test_ana_seed_has_at_least_four_assigned_cases(db_session):
    where = CaseManagerCase.assigned_to == uuid.UUID(ANA.user_id)
    assert _count(db_session, CaseManagerCase, where) >= 4


def test_outro_seed_has_at_least_three_assigned_cases(db_session):
    where = CaseManagerCase.assigned_to == uuid.UUID(OUTRO.user_id)
    assert _count(db_session, CaseManagerCase, where) >= 3


@pytest.mark.parametrize("model", [AnalyticsReport, InvestigatorEntity, CaseManagerCase])
def test_seed_created_at_is_timezone_aware(db_session, model):
    created_at = db_session.scalars(select(model.created_at).limit(1)).one()
    assert created_at.tzinfo is not None


def test_analytics_seed_spans_at_least_three_distinct_months(db_session):
    month = func.date_trunc("month", AnalyticsReport.created_at)
    distinct_months = db_session.scalars(select(month).distinct()).all()
    assert len(distinct_months) >= 3


def test_audit_accepts_denied_row_with_null_app_and_count(db_session):
    denied = SearchAuditLog(
        user_id=uuid.UUID(CARLOS.user_id),
        app=None,
        origin_app="analytics",
        query="empresa aurora",
        results_count=None,
        status="denied",
    )
    db_session.add(denied)
    db_session.flush()
    db_session.refresh(denied)
    assert denied.timestamp.tzinfo is not None  # server default filled it, tz-aware


def test_audit_rejects_unknown_status_value(db_session):
    db_session.add(
        SearchAuditLog(
            user_id=uuid.UUID(CARLOS.user_id),
            origin_app="analytics",
            query="empresa aurora",
            status="invalid",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_trigram_gin_indexes_exist_after_migration(db_session):
    rows = db_session.execute(
        text("SELECT indexname, tablename, indexdef FROM pg_indexes WHERE indexname = ANY(:names)"),
        {"names": list(TRIGRAM_INDEXES)},
    ).all()
    assert {row.indexname: row.tablename for row in rows} == TRIGRAM_INDEXES
    for row in rows:
        assert "USING gin" in row.indexdef
        assert "gin_trgm_ops" in row.indexdef


def test_analytics_ilike_can_use_trigram_index(db_session):
    # With only 10 seed rows the planner will always prefer a seq scan, so a
    # plain EXPLAIN proves nothing about the index. SET LOCAL enable_seqscan =
    # off forces the planner to consider index paths; if the plan then uses the
    # trgm index, the index is *usable* for this exact query shape — which is
    # the honest claim at toy scale (planner *preference* only emerges with
    # production volume). SET LOCAL dies with the fixture's rolled-back
    # transaction, so nothing leaks into other tests.
    db_session.execute(text("SET LOCAL enable_seqscan = off"))
    # Same query shape the Analytics strategy emits: ILIKE with escaped pattern.
    pattern = like_pattern("aurora")
    plan = "\n".join(
        line
        for (line,) in db_session.execute(
            text(
                "EXPLAIN SELECT id FROM analytics_reports "
                f"WHERE content ILIKE '{pattern}' ESCAPE '{LIKE_ESCAPE_CHAR}'"
            )
        )
    )
    assert "ix_analytics_reports_content_trgm" in plan
