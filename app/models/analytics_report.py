import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid7


class AnalyticsReport(Base):
    __tablename__ = "analytics_reports"
    __table_args__ = (
        # Trigram GIN serving the Analytics strategy's ILIKE '%termo%' on
        # content (T-11); mirrored from the migration so `alembic check` is
        # drift-free — the strategy itself doesn't know the index exists.
        Index(
            "ix_analytics_reports_content_trgm",
            "content",
            postgresql_using="gin",
            postgresql_ops={"content": "gin_trgm_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    title: Mapped[str]
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
