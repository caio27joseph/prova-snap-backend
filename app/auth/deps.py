"""JWT authentication dependencies (T-04) — deliberately DB-free.

Implements the strict error taxonomy of docs/JWT_STRUCTURE.md (Decisão 9):
401 = the token is not trustworthy, decided BEFORE looking at permissions;
403 = trusted token without any `<app>:search` permission.
"""

from typing import Annotated, Any

import jwt
from fastapi import Depends, Header, HTTPException

from app.auth.context import AuthContext
from app.config import KNOWN_CLIENTS, settings


def _unauthorized(reason: str) -> HTTPException:
    # `reason` is a coarse category only ("invalid token", never "bad signature"
    # vs "missing sub"): detailed 401 bodies would let a caller probe the
    # verification pipeline check by check.
    return HTTPException(
        status_code=401,
        detail=reason,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_auth_context(
    authorization: Annotated[str | None, Header()] = None,
) -> AuthContext:
    if authorization is None:
        raise _unauthorized("not authenticated")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized("not authenticated")

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            # Pinned server-side, never read from the token header: trusting the
            # header's `alg` is the classic algorithm-confusion vulnerability.
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "azp", "resource_access"]},
        )
    except jwt.ExpiredSignatureError:
        # Expired is the one category worth distinguishing: it tells a
        # legitimate client to refresh, and reveals nothing to an attacker.
        raise _unauthorized("token expired") from None
    except jwt.InvalidTokenError:
        # Covers DecodeError (not a JWT), bad signature and missing required
        # claims — all collapse into one opaque category on purpose.
        raise _unauthorized("invalid token") from None

    azp = payload["azp"]
    if azp not in KNOWN_CLIENTS:
        # azp is part of token *trust*, not permissions: a real Keycloak setup
        # would reject an unknown client at audience validation, so an unknown
        # azp is 401, never 403 (Decisão 9).
        raise _unauthorized("invalid token")

    permissions = _normalize_permissions(payload["resource_access"])

    return AuthContext(
        user_id=payload["sub"],
        origin_app=KNOWN_CLIENTS[azp],
        permissions=permissions,
    )


def _normalize_permissions(resource_access: Any) -> tuple[str, ...]:
    """Keycloak `resource_access.<client>.roles` -> flat `<app>:<role>` tuple
    (Decisão 2: single strict format, normalized here and nowhere else)."""
    if not isinstance(resource_access, dict):
        raise _unauthorized("invalid token")

    permissions: list[str] = []
    # Iterating KNOWN_CLIENTS (not the token) is a strict allowlist: clients we
    # don't know are skipped entirely — forward-compatible with unrelated
    # clients sharing the realm, and their entries can't inject permissions.
    for client_id, app_name in KNOWN_CLIENTS.items():
        access = resource_access.get(client_id)
        if access is None:
            continue
        roles = access.get("roles") if isinstance(access, dict) else None
        if not isinstance(roles, list) or not all(isinstance(r, str) for r in roles):
            raise _unauthorized("invalid token")
        permissions.extend(f"{app_name}:{role}" for role in roles)
    return tuple(permissions)


def require_search_permission(
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> AuthContext:
    if not context.search_apps:
        # The audit row for this 403 (Decisão 6) is written by the search
        # endpoint layer (T-05): this dependency is deliberately DB-free.
        raise HTTPException(
            status_code=403,
            detail="no search permission in any application",
        )
    return context
