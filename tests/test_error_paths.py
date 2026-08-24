"""Error-path tests closing the docs/TEST_STRATEGY.md matrix (ticket T-06).

Covers the two rows no other file exercises — "Banco indisponível" (controlled
503) and "Falha no audit log não derruba a busca" — plus end-to-end proof of
the LIKE-wildcard escaping the migration seed plants fixtures for ("100%" in
one report content and one ANA case title vs "R$ 1000,00" in another content).
"""

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.auth.mock_users import ANA, MARIA, MockUser
from app.db import get_audit_db, get_db
from app.main import app as fastapi_app
from app.services.search.text import escape_like, like_pattern
from tests.token_helpers import make_token

SEARCH_URL = "/api/v1/search"


def _auth(user: MockUser, **kwargs) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(user, **kwargs)}"}


# --- Matrix row: "Banco indisponível" → 503 with controlled body --------------


@pytest.fixture
def db_down_client():
    """Client whose DB dependencies fail at session acquisition, simulating an
    unreachable Postgres. Auth is deliberately DB-free (Decisão 6), so a valid
    token gets past it and the failure surfaces exactly where a dead database
    would: when the request first needs a session."""

    def _connection_refused():
        raise OperationalError("SELECT 1", {}, ConnectionRefusedError("connection refused"))

    fastapi_app.dependency_overrides[get_db] = _connection_refused
    fastapi_app.dependency_overrides[get_audit_db] = _connection_refused
    try:
        with TestClient(fastapi_app) as test_client:
            yield test_client
    finally:
        fastapi_app.dependency_overrides.pop(get_db, None)
        fastapi_app.dependency_overrides.pop(get_audit_db, None)


def test_db_unavailable_returns_503_with_controlled_body(db_down_client):
    response = db_down_client.post(SEARCH_URL, json={"query": "contas"}, headers=_auth(MARIA))

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}


def test_db_unavailable_body_leaks_no_internals(db_down_client):
    # The controlled body must be the WHOLE body: no traceback, driver name,
    # SQL text or exception class an attacker could fingerprint the stack with.
    response = db_down_client.post(SEARCH_URL, json={"query": "contas"}, headers=_auth(MARIA))

    assert response.status_code == 503
    body = response.text.lower()
    for fragment in ("traceback", "sqlalchemy", "operationalerror", "select 1", "psycopg"):
        assert fragment not in body


def test_search_still_succeeds_with_503_handler_registered(client):
    # Round-trip sanity: the OperationalError handler is registered on the
    # real app object, so a healthy request through the same app must remain
    # untouched — the handler narrows to DB failures, it swallows nothing else.
    response = client.post(SEARCH_URL, json={"query": "contas"}, headers=_auth(MARIA))

    assert response.status_code == 200
    assert response.json()["results"]["analytics"]["total_matched"] == 4


# --- Matrix row: audit failure never breaks the search ------------------------


def test_audit_failure_never_breaks_search(client, db_session, monkeypatch, caplog):
    """Inverse of mandated test 5: together they prove the CLAUDE.md rule
    "audit is always written when possible, never fatal when not"."""

    def _commit_fails():
        raise RuntimeError("simulated audit commit failure")

    # The failure point is the audit session's commit — inside audit._write's
    # guard. Strategies only read and run_search never commits the search
    # session, so breaking commit on the shared test session hits audit only.
    monkeypatch.setattr(db_session, "commit", _commit_fails)

    # conftest runs the Alembic migration in-process, and alembic/env.py's
    # fileConfig() defaults to disable_existing_loggers=True — which silently
    # disables the already-imported audit logger. Re-enable it or caplog sees
    # nothing (harmless in prod, where alembic runs as a separate process).
    monkeypatch.setattr(logging.getLogger("app.services.audit"), "disabled", False)

    with caplog.at_level(logging.ERROR, logger="app.services.audit"):
        response = client.post(SEARCH_URL, json={"query": "contas"}, headers=_auth(MARIA))

    assert response.status_code == 200
    assert response.json()["results"]["analytics"]["total_matched"] == 4
    assert any(
        record.levelno == logging.ERROR and "audit write failed" in record.getMessage()
        for record in caplog.records
    )


# --- LIKE-wildcard escaping (Decisão 7), end to end via the seed fixtures -----


def test_percent_in_query_is_literal_for_analytics(client):
    # Seed plants "100%" in one report content (Mar/2026) and "R$ 1000,00" in
    # another (Apr/2026): a naive unescaped LIKE '%100%%' would match both;
    # escaping must match exactly the literal "100%" report.
    response = client.post(SEARCH_URL, json={"query": "100%"}, headers=_auth(MARIA))

    assert response.status_code == 200
    section = response.json()["results"]["analytics"]
    assert section["total_matched"] == 1
    assert section["by_month"] == {"2026-03": 1}


def test_percent_in_query_is_literal_for_case_manager(client):
    response = client.post(
        SEARCH_URL, json={"query": "100%"}, headers=_auth(ANA, azp="case-manager-api")
    )

    assert response.status_code == 200
    items = response.json()["results"]["case-manager"]["items"]
    assert [item["title"] for item in items] == ["Caso 100% digital — fraude em leilão eletrônico"]


def test_escape_like_neutralizes_every_wildcard():
    assert escape_like("100%") == "100\\%"
    assert escape_like("a_b") == "a\\_b"
    # Backslash is doubled FIRST, or the escapes added for % and _ would then
    # be re-escaped into literals.
    assert escape_like("c:\\dir") == "c:\\\\dir"
    assert like_pattern("50%_\\") == "%50\\%\\_\\\\%"
