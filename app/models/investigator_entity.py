import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid7


class InvestigatorEntity(Base):
    __tablename__ = "investigator_entities"
    __table_args__ = (
        # Filter column: every Investigator search runs WHERE type IN (<searchable>).
        Index("ix_investigator_entities_type", "type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    # Plain varchar, deliberately no CHECK constraint: the search layer filters by
    # the allowed-type list (pessoa, empresa, transacao, documento) and the table
    # may store other types; the filter is the boundary, and the seed's 'veiculo'
    # row exists to prove non-searchable types never leak into results.
    type: Mapped[str]
    name: Mapped[str]
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
