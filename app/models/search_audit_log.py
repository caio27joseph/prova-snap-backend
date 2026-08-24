import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid7


class SearchAuditLog(Base):
    """Audit trail — one row per app actually searched; a 403 writes a single
    'denied' row with app/results_count NULL (design in AI log, Decisão 6)."""

    __tablename__ = "search_audit_log"
    __table_args__ = (
        CheckConstraint("status IN ('ok', 'denied')", name="ck_search_audit_log_status"),
        # Filter columns for the two forensic questions the trail must answer
        # cheaply: "what did user X search, when?" and "who touched app Y's data
        # this month?" (Decisão 6).
        Index("ix_search_audit_log_user_id_timestamp", "user_id", "timestamp"),
        Index("ix_search_audit_log_app_timestamp", "app", "timestamp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    # Verified `sub` claim only — 401 (unverified identity) never writes here.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # Data domain searched. NULL on denied rows: a 403 is decided before any
    # app is searched, so there is no domain to attribute (Decisão 6).
    app: Mapped[str | None]
    # Extension over the exam's minimal schema (Decisão 6): the client the user
    # came from (token azp) — distinct from `app` once one search spans N apps.
    origin_app: Mapped[str]
    query: Mapped[str]
    # Extension (Decisão 6): lets compliance answer "how many records did the
    # user see?" without joins. NULL on denied rows — nothing was returned.
    results_count: Mapped[int | None]
    # Extension (Decisão 6): 'ok' | 'denied' — makes denied attempts (403)
    # first-class audit facts instead of app-log archaeology.
    status: Mapped[str]
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
