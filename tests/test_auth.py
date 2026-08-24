"""Auth dependency tests (T-04) — deliberately DB-free.

A minimal probe app (not app.main) exercises get_auth_context and
require_search_permission in isolation: no database, no other routers, so the
whole 401/403 taxonomy of docs/JWT_STRUCTURE.md runs without infrastructure.
"""

from typing import Annotated

import httpx
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.auth.deps import get_auth_context, require_search_permission
from app.auth.mock_users import ANA, CARLOS, JOAO, MARIA
from tests.token_helpers import make_token

probe_app = FastAPI()


@probe_app.get("/probe")
def probe(ctx: Annotated[AuthContext, Depends(get_auth_context)]) -> dict:
    return {
        "user_id": ctx.user_id,
        "origin_app": ctx.origin_app,
        "permissions": list(ctx.permissions),
    }


@probe_app.get("/probe-search")
def probe_search(ctx: Annotated[AuthContext, Depends(require_search_permission)]) -> dict:
    return {"search_apps": list(ctx.search_apps)}


client = TestClient(probe_app)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _assert_401(response: httpx.Response) -> None:
    assert response.status_code == 401
    # RFC 6750: every 401 must tell the client which auth scheme to use.
    assert response.headers.get("WWW-Authenticate") == "Bearer"


# --- 401: the token is not trustworthy ---------------------------------------


def test_missing_authorization_header_returns_401():
    _assert_401(client.get("/probe"))


def test_non_bearer_scheme_returns_401():
    _assert_401(client.get("/probe", headers={"Authorization": "Basic xyz"}))


def test_garbage_token_returns_401():
    _assert_401(client.get("/probe", headers=_bearer("not.a.jwt")))


def test_wrong_signature_returns_401():
    token = make_token(JOAO, secret="wrong-secret")
    _assert_401(client.get("/probe", headers=_bearer(token)))


def test_expired_token_returns_401():
    token = make_token(JOAO, expires_in=-60)
    _assert_401(client.get("/probe", headers=_bearer(token)))


def test_missing_sub_claim_returns_401():
    token = make_token(JOAO, drop_claims=("sub",))
    _assert_401(client.get("/probe", headers=_bearer(token)))


def test_missing_azp_claim_returns_401():
    token = make_token(JOAO, drop_claims=("azp",))
    _assert_401(client.get("/probe", headers=_bearer(token)))


def test_missing_resource_access_claim_returns_401():
    token = make_token(JOAO, drop_claims=("resource_access",))
    _assert_401(client.get("/probe", headers=_bearer(token)))


def test_unknown_azp_returns_401():
    token = make_token(JOAO, azp="unknown-app")
    _assert_401(client.get("/probe", headers=_bearer(token)))


def test_malformed_resource_access_shape_returns_401():
    token = make_token(JOAO, resource_access={"analytics-api": {"roles": "search"}})
    _assert_401(client.get("/probe", headers=_bearer(token)))


def test_untrusted_token_on_search_route_returns_401_not_403():
    # Taxonomy order (Decisão 9): trust is decided before permissions, so an
    # expired token from the zero-permission user must still be 401, never 403.
    token = make_token(CARLOS, expires_in=-60)
    _assert_401(client.get("/probe-search", headers=_bearer(token)))


# --- 403: trusted token, no search permission anywhere -----------------------


def test_no_search_permission_returns_403():
    response = client.get("/probe-search", headers=_bearer(make_token(CARLOS)))
    assert response.status_code == 403


# --- 200: trusted tokens produce a normalized AuthContext --------------------


def test_valid_token_returns_normalized_context():
    response = client.get("/probe", headers=_bearer(make_token(JOAO)))
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == JOAO.user_id
    assert body["origin_app"] == "analytics"
    assert set(body["permissions"]) >= {
        "analytics:search",
        "analytics:viewer",
        "investigator:search",
        "investigator:senior-investigator",
    }


def test_permissions_limited_to_granted_clients():
    response = client.get("/probe", headers=_bearer(make_token(MARIA)))
    assert response.status_code == 200
    permissions = response.json()["permissions"]
    assert permissions
    assert not any(p.startswith("investigator:") for p in permissions)


def test_unknown_client_in_resource_access_is_ignored():
    token = make_token(
        JOAO,
        resource_access={
            "analytics-api": {"roles": ["viewer", "search"]},
            "billing-api": {"roles": ["admin", "search"]},
        },
    )
    response = client.get("/probe", headers=_bearer(token))
    assert response.status_code == 200
    permissions = response.json()["permissions"]
    assert "analytics:search" in permissions
    assert not any(p.startswith("billing") for p in permissions)


def test_search_permission_grants_access_to_search_route():
    token = make_token(ANA, azp="case-manager-api")
    response = client.get("/probe-search", headers=_bearer(token))
    assert response.status_code == 200
    assert response.json()["search_apps"] == ["case-manager"]
