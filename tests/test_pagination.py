"""Cursor pagination on POST /api/v1/search (T-12, Parte 4 improvement #2).

Traversal tests insert their own matching rows through `db_session` (shared
with the app by the client fixture, rolled back per test) under a token that
no seed name/title contains — the tests fully control the matching set instead
of depending on how many seed rows a Portuguese substring happens to hit.
"""

import uuid

import pytest
from sqlalchemy import select

from app.auth.mock_users import ANA, MARIA, OUTRO, PEDRO, MockUser
from app.config import SEARCH_RESULT_LIMIT
from app.models import CaseManagerCase, InvestigatorEntity
from app.models.base import uuid7
from tests.token_helpers import make_token

SEARCH_URL = "/api/v1/search"
# Deliberately absent from every seed name/title.
TOKEN = "pagx"


def _auth(user: MockUser, **kwargs) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(user, **kwargs)}"}


def _add_entities(db_session, count: int, start: int = 0) -> list[InvestigatorEntity]:
    rows = [
        InvestigatorEntity(
            id=uuid7(),
            type="pessoa",
            name=f"Entidade {TOKEN} {start + i:02d}",
            data={"seq": start + i},
        )
        for i in range(count)
    ]
    db_session.add_all(rows)
    db_session.flush()
    return rows


def _post(client, user: MockUser, body: dict, **auth_kwargs):
    return client.post(SEARCH_URL, json=body, headers=_auth(user, **auth_kwargs))


def _walk(client, user: MockUser, query: str, limit: int, section: str, **auth_kwargs):
    """Follow next_cursor until exhaustion; returns the list of item-pages."""
    pages: list[list[dict]] = []
    cursor: str | None = None
    while True:
        body: dict = {"query": query, "limit": limit}
        if cursor is not None:
            body["cursors"] = {section: cursor}
        response = _post(client, user, body, **auth_kwargs)
        assert response.status_code == 200
        payload = response.json()["results"][section]
        pages.append(payload["items"])
        cursor = payload["next_cursor"]
        if cursor is None:
            return pages


# --- Traversal invariants -----------------------------------------------------


def test_full_traversal_matches_unpaginated_set_without_skips_or_repeats(client, db_session):
    _add_entities(db_session, 8)

    pages = _walk(client, PEDRO, TOKEN, limit=3, section="investigator")

    assert [len(page) for page in pages] == [3, 3, 2]  # 8 rows, lookahead stops at page 3
    walked_ids = [item["id"] for page in pages for item in page]
    assert len(walked_ids) == len(set(walked_ids))  # no repeats
    expected_ids = [
        str(row_id)
        for row_id in db_session.execute(
            select(InvestigatorEntity.id)
            .where(InvestigatorEntity.name.ilike(f"%{TOKEN}%"))
            .order_by(InvestigatorEntity.id)
        ).scalars()
    ]
    assert walked_ids == expected_ids  # no skips, and keyset order preserved


def test_insert_after_cursor_position_appears_in_a_later_page(client, db_session):
    initial = _add_entities(db_session, 4)

    body = {"query": TOKEN, "limit": 2}
    first = _post(client, PEDRO, body).json()["results"]["investigator"]
    assert [item["id"] for item in first["items"]] == [str(r.id) for r in initial[:2]]
    cursor = first["next_cursor"]
    assert cursor is not None

    # Mid-traversal insert: a fresh UUIDv7 id timestamps "now", so it sorts
    # after everything already in the table — i.e. after the cursor position.
    late = _add_entities(db_session, 1, start=90)[0]

    remaining: list[str] = []
    while cursor is not None:
        section = _post(
            client, PEDRO, {"query": TOKEN, "limit": 2, "cursors": {"investigator": cursor}}
        ).json()["results"]["investigator"]
        remaining.extend(item["id"] for item in section["items"])
        cursor = section["next_cursor"]

    assert str(late.id) in remaining  # the concurrent insert is picked up
    # No-skip/no-repeat: every row present at traversal start seen exactly once.
    seen = [item["id"] for item in first["items"]] + remaining
    assert sorted(seen) == sorted([str(r.id) for r in initial] + [str(late.id)])
    assert len(seen) == len(set(seen))


def test_insert_before_cursor_position_never_breaks_the_traversal(client, db_session):
    """A row backdated behind the cursor is invisible to the ongoing traversal
    (keyset semantics: the cursor is a position, not a snapshot), but the rows
    present at traversal start are still each seen exactly once. In production
    this case cannot even occur — UUIDv7 ids generated at insert time always
    sort after the cursor — so the id is fabricated here to prove the invariant."""
    initial = _add_entities(db_session, 4)

    first = _post(client, PEDRO, {"query": TOKEN, "limit": 2}).json()["results"]["investigator"]
    cursor = first["next_cursor"]

    backdated = InvestigatorEntity(
        id=uuid.UUID("00000000-0000-7000-8000-000000000001"),  # sorts before all seed/test ids
        type="pessoa",
        name=f"Entidade {TOKEN} retroativa",
        data={"seq": -1},
    )
    db_session.add(backdated)
    db_session.flush()

    remaining: list[str] = []
    while cursor is not None:
        section = _post(
            client, PEDRO, {"query": TOKEN, "limit": 2, "cursors": {"investigator": cursor}}
        ).json()["results"]["investigator"]
        remaining.extend(item["id"] for item in section["items"])
        cursor = section["next_cursor"]

    seen = [item["id"] for item in first["items"]] + remaining
    assert str(backdated.id) not in seen  # behind the cursor: out of this traversal
    assert sorted(seen) == sorted(str(r.id) for r in initial)  # exactly once each
    # A NEW traversal starts before the backdated row, so it does surface it.
    fresh = _walk(client, PEDRO, TOKEN, limit=3, section="investigator")
    assert fresh[0][0]["id"] == str(backdated.id)


def test_next_cursor_is_none_on_exactly_full_final_page(client):
    # Seed: "aurora" matches exactly 2 investigator entities. With limit=2 the
    # single page is exactly full — the limit+1 lookahead must still report
    # next_cursor None instead of dangling an empty extra page.
    response = _post(client, PEDRO, {"query": "aurora", "limit": 2})

    assert response.status_code == 200
    section = response.json()["results"]["investigator"]
    assert len(section["items"]) == 2
    assert section["next_cursor"] is None


def test_case_manager_pagination_keeps_ownership_filter_on_every_page(client, db_session):
    # Seed: "de" matches all 4 of ANA's titles and several of OUTRO/JOAO's —
    # the traversal must page through ANA's 4 and never leak the others.
    pages = _walk(client, ANA, "de", limit=2, section="case-manager", azp="case-manager-api")

    assert [len(page) for page in pages] == [2, 2]
    for page in pages:
        assert all(item["assigned_to"] == ANA.user_id for item in page)
        assert all(item["assigned_to"] != OUTRO.user_id for item in page)
    walked_ids = [item["id"] for page in pages for item in page]
    expected_ids = [
        str(row_id)
        for row_id in db_session.execute(
            select(CaseManagerCase.id)
            .where(
                CaseManagerCase.assigned_to == ANA.user_id,
                CaseManagerCase.title.ilike("%de%"),
            )
            .order_by(CaseManagerCase.id)
        ).scalars()
    ]
    assert walked_ids == expected_ids


# --- Analytics and scope ------------------------------------------------------


def test_analytics_section_is_unaffected_by_pagination_params(client):
    baseline = _post(client, MARIA, {"query": "contas"})
    paginated = _post(client, MARIA, {"query": "contas", "limit": 1})

    assert baseline.status_code == paginated.status_code == 200
    assert baseline.json()["results"]["analytics"] == paginated.json()["results"]["analytics"]
    assert paginated.json()["results"]["analytics"]["total_matched"] == 4


def test_stray_cursor_for_unpermitted_app_is_silently_unused(client):
    # Permissions decide scope, cursors only position within it: PEDRO has no
    # case-manager access, so that cursor is not an error (a 422/403 here
    # would let cursor validation probe which apps deny the user).
    response = _post(client, PEDRO, {"query": "aurora", "cursors": {"case-manager": str(uuid7())}})

    assert response.status_code == 200
    body = response.json()
    assert body["apps_searched"] == ["investigator"]
    assert "case-manager" not in body["results"]


# --- Request validation (422) -------------------------------------------------


@pytest.mark.parametrize(
    "extra",
    [
        pytest.param({"cursors": {"unknown-app": str(uuid7())}}, id="unknown cursor key"),
        pytest.param({"cursors": {"analytics": str(uuid7())}}, id="analytics is not paginated"),
        pytest.param({"cursors": {"investigator": "not-a-uuid"}}, id="non-UUID cursor value"),
        pytest.param({"limit": 0}, id="limit below 1"),
        pytest.param({"limit": SEARCH_RESULT_LIMIT + 1}, id="limit above the resource cap"),
    ],
)
def test_invalid_pagination_params_return_422(client, extra):
    response = _post(client, PEDRO, {"query": "aurora", **extra})
    assert response.status_code == 422
