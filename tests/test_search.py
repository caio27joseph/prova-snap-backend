"""POST /api/v1/search — the 5 mandated tests plus the per-app rules (T-05).

All assertions run against the deterministic Alembic seed (tests/conftest.py
applies the migration to a dedicated test DB), so expected totals and month
buckets are exact values, not fuzzy checks. Audit rows are visible through
`db_session` because the client fixture points both DB dependencies at it.
"""

import uuid

from sqlalchemy import select

from app.auth.mock_users import ANA, CARLOS, JOAO, MARIA, OUTRO, PEDRO, MockUser
from app.models import SearchAuditLog
from tests.token_helpers import make_token

SEARCH_URL = "/api/v1/search"


def _auth(user: MockUser, **kwargs) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(user, **kwargs)}"}


def _audit_rows(db_session) -> list[SearchAuditLog]:
    return list(db_session.execute(select(SearchAuditLog)).scalars())


# --- The 5 mandated tests (docs/TEST_STRATEGY.md, enunciado) -----------------


def test_mandated_1_analytics_permission_gets_only_aggregated_analytics(client):
    """Mandated #1: user with analytics:search receives ONLY Analytics data,
    aggregated, no sensitive detail."""
    response = client.post(SEARCH_URL, json={"query": "contas"}, headers=_auth(MARIA))

    assert response.status_code == 200
    body = response.json()
    assert body["apps_searched"] == ["analytics"]
    assert list(body["results"].keys()) == ["analytics"]
    # Seed: "contas" appears in the content of 4 reports (Jan/Mar/Apr/Jun 2026).
    assert body["results"]["analytics"]["total_matched"] == 4


def test_mandated_2_investigator_permission_gets_full_data(client):
    """Mandated #2: user with investigator:search receives Investigator
    results with complete data."""
    response = client.post(SEARCH_URL, json={"query": "aurora"}, headers=_auth(PEDRO))

    assert response.status_code == 200
    body = response.json()
    assert list(body["results"].keys()) == ["investigator"]
    items = body["results"]["investigator"]["items"]
    # Seed: two entities named *Aurora* (empresa + transacao), ordered by id.
    assert [item["name"] for item in items] == [
        "Aurora Comércio de Alimentos LTDA",
        "TED 2026-0114 Aurora para Maré Alta",
    ]
    for item in items:
        assert isinstance(item["data"], dict) and item["data"]  # full data present
        assert set(item) == {"id", "type", "name", "data", "created_at"}


def test_mandated_3_both_permissions_get_aggregated_response(client):
    """Mandated #3: user with both permissions receives results aggregated
    from both sources (and nothing from Case Manager)."""
    response = client.post(SEARCH_URL, json={"query": "aurora"}, headers=_auth(JOAO))

    assert response.status_code == 200
    body = response.json()
    assert body["apps_searched"] == ["analytics", "investigator"]
    assert set(body["results"]) == {"analytics", "investigator"}
    assert "case-manager" not in body["results"]
    # "aurora" is in one report's CONTENT (the other seed mention is in a
    # title, which Analytics deliberately does not search) and in two names.
    assert body["results"]["analytics"]["total_matched"] == 1
    assert len(body["results"]["investigator"]["items"]) == 2


def test_mandated_4_no_search_permission_returns_403(client):
    """Mandated #4: authenticated user without any search permission → 403."""
    response = client.post(SEARCH_URL, json={"query": "aurora"}, headers=_auth(CARLOS))

    assert response.status_code == 403
    assert response.json()["detail"] == "no search permission in any application"


def test_mandated_5_successful_search_writes_audit_row(client, db_session):
    """Mandated #5: a successful search writes the audit row (user_id, app,
    query, timestamp — plus the Decisão 6 extensions)."""
    response = client.post(SEARCH_URL, json={"query": "contas"}, headers=_auth(MARIA))
    assert response.status_code == 200

    rows = _audit_rows(db_session)
    assert len(rows) == 1
    row = rows[0]
    assert row.user_id == uuid.UUID(MARIA.user_id)
    assert row.app == "analytics"
    assert row.origin_app == "analytics"  # from token azp=analytics-api
    assert row.query == "contas"
    assert row.status == "ok"
    assert isinstance(row.results_count, int) and row.results_count >= 0
    assert row.timestamp is not None


# --- Per-app rules (ticket T-05) ---------------------------------------------


def test_case_manager_returns_only_own_cases(client):
    # Seed: "rede" matches one ANA title AND one OUTRO title — the ownership
    # filter must keep only ANA's case.
    response = client.post(
        SEARCH_URL, json={"query": "rede"}, headers=_auth(ANA, azp="case-manager-api")
    )

    assert response.status_code == 200
    items = response.json()["results"]["case-manager"]["items"]
    assert 1 <= len(items) <= 4  # ANA owns 4 cases in total
    assert all(item["assigned_to"] == ANA.user_id for item in items)
    titles = [item["title"] for item in items]
    assert titles == ["Lavagem de dinheiro em rede de postos"]
    assert "Sonegação fiscal em rede varejista" not in titles  # OUTRO's case
    assert all(item["assigned_to"] != OUTRO.user_id for item in items)


def test_investigator_non_searchable_type_never_returned(client):
    # Seed: "volvo" only matches the 'veiculo' entity, which is outside the
    # searchable-types allowlist — the result must be empty.
    response = client.post(SEARCH_URL, json={"query": "volvo"}, headers=_auth(PEDRO))

    assert response.status_code == 200
    assert response.json()["results"]["investigator"]["items"] == []


def test_analytics_section_cannot_leak_titles_or_content(client):
    """Negative assertion of Decisão 7: the serialized analytics section has
    exactly the aggregate keys — report title/content cannot appear."""
    response = client.post(SEARCH_URL, json={"query": "aurora"}, headers=_auth(MARIA))

    assert response.status_code == 200
    section = response.json()["results"]["analytics"]
    assert set(section.keys()) == {"total_matched", "by_month"}


def test_two_app_search_writes_one_audit_row_per_app(client, db_session):
    response = client.post(SEARCH_URL, json={"query": "aurora"}, headers=_auth(JOAO))
    assert response.status_code == 200

    rows = _audit_rows(db_session)
    assert {row.app for row in rows} == {"analytics", "investigator"}
    assert all(row.origin_app == "analytics" for row in rows)
    assert all(row.status == "ok" for row in rows)
    assert all(row.user_id == uuid.UUID(JOAO.user_id) for row in rows)
    by_app = {row.app: row.results_count for row in rows}
    assert by_app == {"analytics": 1, "investigator": 2}


def test_denied_search_writes_single_denied_audit_row(client, db_session):
    response = client.post(SEARCH_URL, json={"query": "aurora"}, headers=_auth(CARLOS))
    assert response.status_code == 403

    rows = _audit_rows(db_session)
    assert len(rows) == 1
    row = rows[0]
    assert row.user_id == uuid.UUID(CARLOS.user_id)
    assert row.app is None
    assert row.origin_app == "analytics"
    assert row.query == "aurora"
    assert row.results_count is None
    assert row.status == "denied"


def test_analytics_by_month_spans_multiple_buckets(client):
    # Seed: "contas" matches report content in 4 distinct months of 2026.
    response = client.post(SEARCH_URL, json={"query": "contas"}, headers=_auth(MARIA))

    assert response.status_code == 200
    section = response.json()["results"]["analytics"]
    assert section["by_month"] == {"2026-01": 1, "2026-03": 1, "2026-04": 1, "2026-06": 1}
    assert len(section["by_month"]) >= 2
    assert section["total_matched"] == sum(section["by_month"].values())


# --- Query validation (bounds live in app/config.py) -------------------------


def test_query_below_min_length_returns_422(client):
    response = client.post(SEARCH_URL, json={"query": "a"}, headers=_auth(MARIA))
    assert response.status_code == 422


def test_query_above_max_length_returns_422(client):
    response = client.post(SEARCH_URL, json={"query": "x" * 201}, headers=_auth(MARIA))
    assert response.status_code == 422


def test_whitespace_only_query_returns_422(client):
    # Stripped before length validation: spaces are an empty query.
    response = client.post(SEARCH_URL, json={"query": "     "}, headers=_auth(MARIA))
    assert response.status_code == 422


def test_empty_body_returns_422(client):
    response = client.post(SEARCH_URL, json={}, headers=_auth(MARIA))
    assert response.status_code == 422
