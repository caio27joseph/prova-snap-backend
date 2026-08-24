import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.api import health, search
from app.db import engine
from app.observability import setup_observability

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Snap Forensics — Multi-Application Search API",
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(search.router)

# After the routers: instruments HTTP + SQLAlchemy metrics and mounts /metrics
# (T-13 — see app/observability.py for the choices made here).
setup_observability(app, engine)


@app.exception_handler(OperationalError)
async def database_unavailable_handler(request: Request, exc: OperationalError) -> JSONResponse:
    # TEST_STRATEGY matrix row "Banco indisponível": a DB connection failure is
    # an operational condition, not a bug — answer 503 with a fixed, controlled
    # body (never a 500/stacktrace, which would leak internals to the client).
    # The full exception still goes to the server log for operators.
    logger.error("database unavailable: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "database unavailable"})
