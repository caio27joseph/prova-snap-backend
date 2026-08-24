"""Guards the identity contract (app/auth/mock_users.py).

The Alembic seed and the JWT test helper both depend on these invariants;
breaking one here would fail the mandated tests in confusing, indirect ways.
"""

import uuid

import pytest

from app.auth.mock_users import ALL_USERS, ANA, CARLOS, JOAO, MARIA, OUTRO, PEDRO


@pytest.mark.parametrize("user", ALL_USERS, ids=lambda u: u.username)
def test_user_id_is_a_valid_uuid(user):
    uuid.UUID(user.user_id)  # raises on malformed


def test_user_ids_are_unique():
    ids = [u.user_id for u in ALL_USERS]
    assert len(ids) == len(set(ids))


def test_usernames_are_unique():
    names = [u.username for u in ALL_USERS]
    assert len(names) == len(set(names))


@pytest.mark.parametrize(
    ("user", "expected_clients"),
    [
        pytest.param(MARIA, {"analytics-api"}, id="mandated-1-analytics-only"),
        pytest.param(PEDRO, {"investigator-api"}, id="mandated-2-investigator-only"),
        pytest.param(JOAO, {"analytics-api", "investigator-api"}, id="mandated-3-multi-app"),
        pytest.param(CARLOS, set(), id="mandated-4-no-permissions-403"),
        pytest.param(ANA, {"case-manager-api"}, id="case-assignment-owner"),
        pytest.param(OUTRO, {"case-manager-api"}, id="case-assignment-other-user"),
    ],
)
def test_personas_cover_the_mandated_test_matrix(user, expected_clients):
    assert set(user.roles) == expected_clients


def test_case_manager_personas_are_distinct_users():
    assert ANA.user_id != OUTRO.user_id


@pytest.mark.parametrize("user", [u for u in ALL_USERS if u.roles], ids=lambda u: u.username)
def test_every_granted_client_includes_the_search_role(user):
    # the endpoint requires <app>:search — a persona holding an app without
    # 'search' would make seeds/tokens silently test nothing
    for roles in user.roles.values():
        assert "search" in roles
