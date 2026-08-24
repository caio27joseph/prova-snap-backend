"""Request/response contracts for POST /api/v1/search.

Serialization is the security boundary (Decisão 7): each app section is a
strict response model, so "no sensitive detail" is structural — fields that
must not leave the API simply do not exist on the schema.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import QUERY_MAX_LENGTH, QUERY_MIN_LENGTH, SEARCH_RESULT_LIMIT

# Sections that return rows and therefore accept a cursor. Analytics is
# deliberately absent: it returns aggregates, not rows — paginating it is a
# contract error, so an "analytics" cursor fails loud (422) instead of being
# silently ignored.
PAGINATED_APPS = frozenset({"investigator", "case-manager"})


class SearchRequest(BaseModel):
    query: str = Field(min_length=QUERY_MIN_LENGTH, max_length=QUERY_MAX_LENGTH)
    # The fixed cap stays as the resource guard (app/config.py): callers may
    # only page smaller than SEARCH_RESULT_LIMIT, never larger.
    limit: int = Field(default=SEARCH_RESULT_LIMIT, ge=1, le=SEARCH_RESULT_LIMIT)
    # Per-section keyset cursors, keyed by app name; each value is the
    # `next_cursor` echoed from that section in a previous response.
    cursors: dict[str, str] | None = None

    @field_validator("query", mode="before")
    @classmethod
    def strip_surrounding_whitespace(cls, value: Any) -> Any:
        # Stripped BEFORE the length bounds run: a query of spaces is an empty
        # query and must fail min_length (422), not reach the database.
        return value.strip() if isinstance(value, str) else value

    @field_validator("cursors")
    @classmethod
    def check_cursor_keys_and_values(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is None:
            return value
        for app_name, cursor in value.items():
            if app_name not in PAGINATED_APPS:
                raise ValueError(
                    f"'{app_name}' is not a paginated section; "
                    f"valid cursor keys: {sorted(PAGINATED_APPS)}"
                )
            try:
                UUID(cursor)
            except ValueError:
                # Cursors are opaque to clients but structurally they are the
                # last item's UUID — anything else can never match a row and
                # is a malformed request, not an empty page.
                raise ValueError(f"cursor for '{app_name}' is not a valid UUID") from None
        return value


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
    # Keyset cursor (docs/ESCALABILIDADE.md): the id of the last item when a
    # next page exists, None on the final page. Echo it back under
    # `cursors["investigator"]` to fetch the next page.
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
