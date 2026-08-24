"""Request/response contracts for POST /api/v1/search.

Serialization is the security boundary (Decisão 7): each app section is a
strict response model, so "no sensitive detail" is structural — fields that
must not leave the API simply do not exist on the schema.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import QUERY_MAX_LENGTH, QUERY_MIN_LENGTH


class SearchRequest(BaseModel):
    query: str = Field(min_length=QUERY_MIN_LENGTH, max_length=QUERY_MAX_LENGTH)

    @field_validator("query", mode="before")
    @classmethod
    def strip_surrounding_whitespace(cls, value: Any) -> Any:
        # Stripped BEFORE the length bounds run: a query of spaces is an empty
        # query and must fail min_length (422), not reach the database.
        return value.strip() if isinstance(value, str) else value


class AnalyticsSection(BaseModel):
    """Aggregate only — title/content fields deliberately do not exist here,
    making a sensitive-detail leak impossible by construction (Decisão 7/9)."""

    total_matched: int
    by_month: dict[str, int]


class InvestigatorItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    name: str
    data: dict[str, Any]
    created_at: datetime


class CaseManagerItem(BaseModel):
    """Metadata only — the case content never enters the schema (exam rule)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    assigned_to: UUID
    status: str
    created_at: datetime


class InvestigatorSection(BaseModel):
    items: list[InvestigatorItem]
    # Always None today: cursor pagination is a prioritized Parte 4
    # improvement; the envelope is already cursor-ready (docs/ESCALABILIDADE.md).
    next_cursor: str | None = None


class CaseManagerSection(BaseModel):
    items: list[CaseManagerItem]
    next_cursor: str | None = None


class SearchResponse(BaseModel):
    query: str
    apps_searched: list[str]
    # Keyed by the canonical app names from KNOWN_CLIENTS ("analytics",
    # "investigator", "case-manager"); only apps actually searched appear.
    results: dict[str, AnalyticsSection | InvestigatorSection | CaseManagerSection]
