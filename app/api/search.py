from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.context import AuthContext
from app.auth.deps import get_auth_context
from app.db import get_audit_db, get_db
from app.schemas.search import SearchRequest, SearchResponse
from app.services.search import run_search

router = APIRouter()


@router.post("/api/v1/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    # get_auth_context, not require_search_permission: the no-permission 403
    # must be audited in the DB (Decisão 6) and the auth dependency is
    # deliberately DB-free — the service owns the denied-then-403 sequence.
    context: Annotated[AuthContext, Depends(get_auth_context)],
    db: Annotated[Session, Depends(get_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> SearchResponse:
    return run_search(context, request, db, audit_db)
