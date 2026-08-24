from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth.context import AuthContext
from app.schemas.search import SearchRequest, SearchResponse
from app.services import audit
from app.services.search.analytics import AnalyticsStrategy
from app.services.search.base import SearchStrategy
from app.services.search.case_manager import CaseManagerStrategy
from app.services.search.investigator import InvestigatorStrategy

_STRATEGIES: dict[str, SearchStrategy] = {
    strategy.app_name: strategy
    for strategy in (AnalyticsStrategy(), InvestigatorStrategy(), CaseManagerStrategy())
}


def run_search(
    context: AuthContext,
    request: SearchRequest,
    db: Session,
    audit_db: Session,
) -> SearchResponse:
    if not context.search_apps:
        # Deliberately NOT require_search_permission (app/auth/deps.py): that
        # dependency is DB-free by design, and this 403 must land in the audit
        # trail (Decisão 6) — so the denied row is written first, then raised.
        audit.record_search_denied(audit_db, context, request.query)
        raise HTTPException(status_code=403, detail="no search permission in any application")

    results = {}
    results_per_app: list[tuple[str, int]] = []
    # A cursor for an app outside the user's permitted scope is silently
    # unused, not an error: permissions decide WHICH apps are searched,
    # cursors only position WITHIN that scope. Rejecting stray cursors would
    # turn cursor validation into a permission probe (a 403-ish signal
    # revealing what exists for other users).
    cursors = request.cursors or {}
    for app_name in context.search_apps:
        section, count = _STRATEGIES[app_name].search(
            db, request.query, context.user_id, cursors.get(app_name), request.limit
        )
        results[app_name] = section
        results_per_app.append((app_name, count))

    audit.record_search_ok(audit_db, context, request.query, results_per_app)
    return SearchResponse(
        query=request.query,
        apps_searched=list(context.search_apps),
        results=results,
    )
