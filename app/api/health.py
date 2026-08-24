from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.db import SessionLocal

router = APIRouter()


@router.get("/health")
def health() -> JSONResponse:
    """Liveness + DB reachability. DB down is a controlled 503, never a stacktrace."""
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except OperationalError:
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "down"})
    return JSONResponse(content={"status": "ok", "database": "up"})
