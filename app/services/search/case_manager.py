from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CaseManagerCase
from app.schemas.search import CaseManagerItem, CaseManagerSection
from app.services.search.text import LIKE_ESCAPE_CHAR, like_pattern


class CaseManagerStrategy:
    app_name = "case-manager"

    def search(
        self, session: Session, query: str, user_id: str, cursor: str | None, limit: int
    ) -> tuple[CaseManagerSection, int]:
        stmt = (
            select(CaseManagerCase)
            .where(
                # Ownership rule: only cases assigned to the requesting
                # user (verified `sub`) are ever visible.
                CaseManagerCase.assigned_to == user_id,
                # Exam rule: metadata only — ILIKE on `title`; case content
                # is not searchable and not returned.
                CaseManagerCase.title.ilike(like_pattern(query), escape=LIKE_ESCAPE_CHAR),
            )
            # Keyset cursor over time-ordered UUIDv7 PKs (Decisão 5); the
            # ownership WHERE above applies on every page, so a cursor can
            # never walk into another user's cases.
            .order_by(CaseManagerCase.id)
            # limit+1 lookahead — see investigator.py for the rationale.
            .limit(limit + 1)
        )
        if cursor is not None:
            stmt = stmt.where(CaseManagerCase.id > UUID(cursor))
        rows = session.execute(stmt).scalars().all()
        items = [CaseManagerItem.model_validate(row) for row in rows[:limit]]
        next_cursor = str(items[-1].id) if len(rows) > limit else None
        return CaseManagerSection(items=items, next_cursor=next_cursor), len(items)
