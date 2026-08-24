from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

# Sync engine by deliberate decision (AI log, Decisão 8): FastAPI runs `def`
# endpoints in a threadpool, and sync keeps fixtures/session handling simple.
# pool_pre_ping: on-premises DBs restart; a stale pooled connection must not
# surface as a 500 on the next request.
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def get_audit_db() -> Generator[Session, None, None]:
    """Second, independent session (same SessionLocal) for audit writes
    (Decisão 6): the audit commit must not depend on, or interfere with, the
    search session's transaction — an audit failure rolls back alone."""
    with SessionLocal() as session:
        yield session
