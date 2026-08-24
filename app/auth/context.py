"""Authenticated request identity, produced by the auth dependency (T-04).

Everything downstream (search service, audit trail) consumes this object and
never touches the raw JWT — swapping the mock issuer for a real Keycloak
changes only the dependency, not this contract (docs/JWT_STRUCTURE.md).
"""

from dataclasses import dataclass

from app.config import KNOWN_CLIENTS


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    origin_app: str
    permissions: tuple[str, ...]

    @property
    def search_apps(self) -> tuple[str, ...]:
        # KNOWN_CLIENTS declaration order, not token order: the grouped search
        # response is assembled per app, and a deterministic order keeps it
        # (and its tests) stable regardless of how the issuer sorted claims.
        return tuple(app for app in KNOWN_CLIENTS.values() if f"{app}:search" in self.permissions)
