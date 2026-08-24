from typing import Protocol

from pydantic import BaseModel
from sqlalchemy.orm import Session


class SearchStrategy(Protocol):
    """One strategy per application behind a single service (CLAUDE.md
    convention): the shared endpoint stays thin and each app's rule set lives
    in its own module. Returns (response section, results_count for audit).

    `cursor`/`limit` are part of the single shared signature even though
    Analytics aggregates instead of listing rows: keeping one Protocol keeps
    the service loop uniform (no isinstance special-casing), and Analytics
    stays honest by asserting it never receives a cursor — see analytics.py.
    """

    app_name: str

    def search(
        self, session: Session, query: str, user_id: str, cursor: str | None, limit: int
    ) -> tuple[BaseModel, int]: ...
