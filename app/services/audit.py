"""Search audit trail writer (Decisão 6).

Hard rule (CLAUDE.md): audit logging must never break the search response.
Every write is wrapped so ANY failure — connection loss, constraint error,
bad data — is logged as an application error and swallowed, trading trail
completeness for availability (trade-off recorded in the AI log).
"""

import logging

from sqlalchemy.orm import Session

from app.auth.context import AuthContext
from app.models import SearchAuditLog
from app.observability import audit_write_failures

logger = logging.getLogger(__name__)


def record_search_ok(
    session: Session,
    context: AuthContext,
    query: str,
    results_per_app: list[tuple[str, int]],
) -> None:
    """One row per app actually searched: `app` is the data domain touched,
    `origin_app` the client the user came from — distinct concepts once a
    single search spans multiple apps (Decisão 6)."""
    _write(
        session,
        [
            SearchAuditLog(
                user_id=context.user_id,
                app=app,
                origin_app=context.origin_app,
                query=query,
                results_count=count,
                status="ok",
            )
            for app, count in results_per_app
        ],
    )


def record_search_denied(session: Session, context: AuthContext, query: str) -> None:
    """A 403 is decided before any app is searched, so there is no domain to
    attribute and nothing was returned: app/results_count stay NULL."""
    _write(
        session,
        [
            SearchAuditLog(
                user_id=context.user_id,
                app=None,
                origin_app=context.origin_app,
                query=query,
                results_count=None,
                status="denied",
            )
        ],
    )


def _write(session: Session, rows: list[SearchAuditLog]) -> None:
    try:
        session.add_all(rows)
        session.commit()
    except Exception:
        logger.exception("audit write failed — search response is preserved (CLAUDE.md rule)")
        try:
            # Metric, not just log line (PARTE3_INCIDENT §7): a silent audit
            # gap in a forensic platform must be alertable. Wrapped because
            # the guard may never raise — not even for its own telemetry.
            audit_write_failures.add(1)
        except Exception:
            logger.exception("audit failure metric increment failed")
        try:
            session.rollback()
        except Exception:
            # A dead connection can make rollback itself raise; the guarantee
            # "audit never breaks the response" must hold even then.
            logger.exception("audit session rollback failed")
