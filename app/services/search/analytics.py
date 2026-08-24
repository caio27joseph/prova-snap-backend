from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AnalyticsReport
from app.schemas.search import AnalyticsSection
from app.services.search.text import LIKE_ESCAPE_CHAR, like_pattern


class AnalyticsStrategy:
    app_name = "analytics"

    def search(
        self, session: Session, query: str, user_id: str, cursor: str | None, limit: int
    ) -> tuple[AnalyticsSection, int]:
        # Analytics matches the single shared Protocol (base.py) rather than
        # being special-cased in the service. A cursor can never legitimately
        # arrive here — the request validator 422s an "analytics" cursor key —
        # so the assert keeps this boundary honest if that guard ever
        # regresses. `limit` is deliberately ignored: aggregates are one row
        # of counts, not a list to cap.
        assert cursor is None, "analytics is not paginated; the schema validator must reject this"
        # Exam rule: Analytics searches `content` ONLY ("busca apenas em
        # conteúdo") — the title column never enters the WHERE clause.
        matched = AnalyticsReport.content.ilike(like_pattern(query), escape=LIKE_ESCAPE_CHAR)
        month = func.to_char(func.date_trunc("month", AnalyticsReport.created_at), "YYYY-MM")
        rows = session.execute(
            select(month, func.count()).where(matched).group_by(month).order_by(month)
        ).all()
        # Total derived from the same grouped scan: one round trip, and
        # total_matched == sum(by_month) holds by construction.
        by_month = {bucket: count for bucket, count in rows}
        total = sum(by_month.values())
        # Aggregate-only section: no LIMIT concept applies, and results_count
        # for the audit trail is the number of matched reports.
        return AnalyticsSection(total_matched=total, by_month=by_month), total
