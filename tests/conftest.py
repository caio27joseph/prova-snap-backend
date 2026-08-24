"""Session-wide test infrastructure (docs/TEST_STRATEGY.md).

Real Postgres, real migrations: the suite runs against a dedicated database
(`prova_test`) that is dropped and rebuilt via `alembic upgrade head` once per
session. The migration seed rows therefore exist in the test DB and are fully
deterministic — tests may rely on them.
"""

import os
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from alembic import command
from app.config import settings
from app.db import get_db
from app.main import app as fastapi_app

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _test_database_url() -> str:
    # Default swaps only the database name, so a bare `pytest` is zero-config on
    # the dev compose stack; TEST_DATABASE_URL overrides everything, which lets
    # parallel worktrees point at their own Postgres instance/port.
    if env_url := os.environ.get("TEST_DATABASE_URL"):
        return env_url
    swapped = make_url(settings.database_url).set(database="prova_test")
    # render_as_string, not str(): str() hides the password as literal "***",
    # which then fails authentication when the URL is reused to connect.
    return swapped.render_as_string(hide_password=False)


TEST_DATABASE_URL = _test_database_url()


def _recreate_test_database() -> None:
    url = make_url(TEST_DATABASE_URL)
    # CREATE/DROP DATABASE need a connection to another DB: use the app's dev
    # database (always present in the compose stack) as the maintenance DB.
    admin_url = url.set(database=make_url(settings.database_url).database)
    admin_engine = create_engine(
        admin_url, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3}
    )
    try:
        with admin_engine.connect() as conn:
            # Drop-and-recreate instead of `downgrade base`: proves `upgrade
            # head` works on a zeroed database every session and does not trust
            # downgrade() to clean up after itself.
            conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    except OperationalError as exc:
        pytest.exit(
            f"Postgres not reachable at {admin_url.host}:{admin_url.port} — "
            f"run `docker compose up -d` first (original error: {exc})",
            returncode=1,
        )
    finally:
        admin_engine.dispose()


def _run_migrations() -> None:
    # Alembic, not Base.metadata.create_all: the migration (DDL + indexes +
    # seed) is itself a deliverable, so the suite must exercise it for real.
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def engine():
    _recreate_test_database()
    _run_migrations()
    engine = create_engine(TEST_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(engine):
    """Each test runs inside an outer transaction that is rolled back at
    teardown: full isolation between tests without rebuilding the schema.
    (Session commits become savepoint releases, so they roll back too.)"""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, autoflush=False)
    try:
        yield session
    finally:
        session.close()
        # A test that provokes a DB error (e.g. constraint violation) may have
        # already invalidated the outer transaction — rolling back twice warns.
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session):
    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(fastapi_app) as test_client:
            yield test_client
    finally:
        fastapi_app.dependency_overrides.pop(get_db, None)
