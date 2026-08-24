from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import SEARCH_RESULT_LIMIT
from app.models import CaseManagerCase
from app.schemas.search import CaseManagerItem, CaseManagerSection
from app.services.search.text import LIKE_ESCAPE_CHAR, like_pattern


class CaseManagerStrategy:
    app_name = "case-manager"

    def search(self, session: Session, query: str, user_id: str) -> tuple[CaseManagerSection, int]:
        rows = (
            session.execute(
                select(CaseManagerCase)
                .where(
                    # Ownership rule: only cases assigned to the requesting
                    # user (verified `sub`) are ever visible.
                    CaseManagerCase.assigned_to == user_id,
                    # Exam rule: metadata only — ILIKE on `title`; case content
                    # is not searchable and not returned.
                    CaseManagerCase.title.ilike(like_pattern(query), escape=LIKE_ESCAPE_CHAR),
                )
                .order_by(CaseManagerCase.id)
                .limit(SEARCH_RESULT_LIMIT)
            )
            .scalars()
            .all()
        )
        items = [CaseManagerItem.model_validate(row) for row in rows]
        return CaseManagerSection(items=items), len(items)
