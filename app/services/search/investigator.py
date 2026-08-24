from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import SEARCH_RESULT_LIMIT
from app.models import InvestigatorEntity
from app.schemas.search import InvestigatorItem, InvestigatorSection
from app.services.search.text import LIKE_ESCAPE_CHAR, like_pattern

# This allowed-list IS the boundary for non-searchable entity types: the table
# has no CHECK constraint on `type` (may hold e.g. 'veiculo'), so rows outside
# this tuple can never reach a search result.
SEARCHABLE_TYPES = ("pessoa", "empresa", "transacao", "documento")


class InvestigatorStrategy:
    app_name = "investigator"

    def search(self, session: Session, query: str, user_id: str) -> tuple[InvestigatorSection, int]:
        rows = (
            session.execute(
                select(InvestigatorEntity)
                .where(
                    InvestigatorEntity.type.in_(SEARCHABLE_TYPES),
                    InvestigatorEntity.name.ilike(like_pattern(query), escape=LIKE_ESCAPE_CHAR),
                )
                # UUIDv7 PKs are time-ordered, so ORDER BY id is a stable
                # chronological order and the future keyset cursor's order.
                .order_by(InvestigatorEntity.id)
                .limit(SEARCH_RESULT_LIMIT)
            )
            .scalars()
            .all()
        )
        items = [InvestigatorItem.model_validate(row) for row in rows]
        return InvestigatorSection(items=items), len(items)
