"""Mock Keycloak user registry.

This module would NOT exist with a real Keycloak: users, credentials and role
assignments would live in the realm. It is the executable counterpart of
docs/JWT_STRUCTURE.md — the fixed UUIDs below are shared by the Alembic seed
(cases assigned to these users) and by the test token helper, so the mandated
Case Manager test ("only cases assigned to the user") closes by construction.

UUIDs are UUIDv7 generated once at authoring time and hardcoded for
deterministic seeds and reproducible test assertions.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MockUser:
    user_id: str  # Keycloak `sub` claim
    username: str
    # client_id -> client roles, exactly as Keycloak's resource_access shape
    roles: dict[str, list[str]] = field(default_factory=dict)


# Personas cover every mandated test case (docs/BACKLOG.md T-04/T-05):
# joao mirrors the exam's own example (Analytics viewer + Investigator senior).
JOAO = MockUser(
    user_id="01a03323-fe61-72b0-9ac6-84f42896edd4",
    username="joao.silva",
    roles={
        "analytics-api": ["viewer", "search"],
        "investigator-api": ["senior-investigator", "search"],
    },
)
MARIA = MockUser(
    user_id="01a03323-fe61-72b0-9ac6-8509308c7812",
    username="maria.santos",
    roles={"analytics-api": ["viewer", "search"]},
)
PEDRO = MockUser(
    user_id="01a03323-fe61-72b0-9ac6-851101980d40",
    username="pedro.lima",
    roles={"investigator-api": ["search"]},
)
ANA = MockUser(
    user_id="01a03323-fe61-72b0-9ac6-8524ead7cf87",
    username="ana.costa",
    roles={"case-manager-api": ["search"]},
)
# Authenticated but with zero search permissions anywhere -> the 403 persona.
CARLOS = MockUser(
    user_id="01a03323-fe61-72b0-9ac6-853dbd1aa14c",
    username="carlos.souza",
    roles={},
)
# Owns cases that must NEVER appear in ANA's results (assignment filter proof).
OUTRO = MockUser(
    user_id="01a03323-fe61-72b0-9ac6-85486f005be6",
    username="outro.usuario",
    roles={"case-manager-api": ["search"]},
)

ALL_USERS = [JOAO, MARIA, PEDRO, ANA, CARLOS, OUTRO]
