from typing import Protocol

from pydantic import BaseModel
from sqlalchemy.orm import Session


class SearchStrategy(Protocol):
    """One strategy per application behind a single service (CLAUDE.md
    convention): the shared endpoint stays thin and each app's rule set lives
    in its own module. Returns (response section, results_count for audit)."""

    app_name: str

    def search(self, session: Session, query: str, user_id: str) -> tuple[BaseModel, int]: ...
