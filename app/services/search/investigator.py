from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InvestigatorEntity
from app.schemas.search import InvestigatorItem, InvestigatorSection
from app.services.search.text import LIKE_ESCAPE_CHAR, like_pattern

# This allowed-list IS the boundary for non-searchable entity types: the table
# has no CHECK constraint on `type` (may hold e.g. 'veiculo'), so rows outside
# this tuple can never reach a search result.
SEARCHABLE_TYPES = ("pessoa", "empresa", "transacao", "documento")


class InvestigatorStrategy:
    app_name = "investigator"

    def search(
        self, session: Session, query: str, user_id: str, cursor: str | None, limit: int
    ) -> tuple[InvestigatorSection, int]:
        stmt = (
            select(InvestigatorEntity)
            .where(
                InvestigatorEntity.type.in_(SEARCHABLE_TYPES),
                InvestigatorEntity.name.ilike(like_pattern(query), escape=LIKE_ESCAPE_CHAR),
            )
            # UUIDv7 PKs are time-ordered (Decisão 5), so ORDER BY id is a
            # stable chronological order and `id > :cursor` is a keyset cursor
            # that neither skips nor repeats rows under concurrent inserts.
            .order_by(InvestigatorEntity.id)
            # limit+1 lookahead: the extra row only answers "is there a next
            # page?" and is never returned. One row more than checking
            # len == limit, but it removes that check's wart — a dangling
            # empty final page whenever the last page is exactly full.
            .limit(limit + 1)
        )
        if cursor is not None:
            stmt = stmt.where(InvestigatorEntity.id > UUID(cursor))
        rows = session.execute(stmt).scalars().all()
        items = [InvestigatorItem.model_validate(row) for row in rows[:limit]]
        next_cursor = str(items[-1].id) if len(rows) > limit else None
        return InvestigatorSection(items=items, next_cursor=next_cursor), len(items)
