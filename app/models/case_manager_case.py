import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid7


class CaseManagerCase(Base):
    __tablename__ = "case_manager_cases"
    __table_args__ = (
        # Filter columns: Case Manager only ever queries WHERE assigned_to = <sub>
        # (ownership rule), optionally narrowed by status.
        Index("ix_case_manager_cases_assigned_to", "assigned_to"),
        Index("ix_case_manager_cases_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    title: Mapped[str]
    # Keycloak `sub` UUID, not username (Decisão 9: usernames are mutable).
    assigned_to: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
