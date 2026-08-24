"""Mock Keycloak token factory for tests.

With a real Keycloak this file would not exist — tokens would come from the
realm's Authorization Code Flow. Payload mirrors docs/JWT_STRUCTURE.md; the
escape hatches (drop_claims, secret, negative expires_in, explicit
resource_access) exist to forge every invalid-token case in the error taxonomy.
"""

import time
from typing import Any

import jwt

from app.auth.mock_users import MockUser
from app.config import settings

ISSUER = "http://keycloak.local/realms/plataforma"


def make_token(
    user: MockUser | None = None,
    *,
    azp: str = "analytics-api",
    expires_in: int = 3600,
    secret: str | None = None,
    drop_claims: tuple[str, ...] = (),
    resource_access: dict[str, Any] | None = None,
    **overrides: Any,
) -> str:
    if resource_access is None:
        roles = user.roles if user is not None else {}
        resource_access = {client: {"roles": list(r)} for client, r in roles.items()}

    now = int(time.time())
    payload: dict[str, Any] = {
        "iss": ISSUER,
        "sub": user.user_id if user else "00000000-0000-0000-0000-000000000000",
        "azp": azp,
        "iat": now,
        "exp": now + expires_in,
        "preferred_username": user.username if user else "anonymous",
        "resource_access": resource_access,
    }
    payload.update(overrides)
    # Dropped AFTER building so callers can remove any claim, including
    # defaults, to forge the missing-required-claim 401 cases.
    for claim in drop_claims:
        payload.pop(claim, None)

    return jwt.encode(
        payload,
        secret if secret is not None else settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
