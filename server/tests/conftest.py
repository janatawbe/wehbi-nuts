from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registers all models on Base.metadata)
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.services.storage import get_upload_root


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """An isolated, in-memory SQLite database for a single test.

    Milestone 2 targets PostgreSQL in production, but tests must not
    require a real local PostgreSQL server. Each test gets a fresh
    schema so tests never leak state into one another.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_sqlite_fk(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)

    # expire_on_commit=False: SQLite has no timezone-aware storage, so a
    # post-commit reload would silently strip tzinfo from timestamp
    # columns. Keeping committed Python objects in place lets us verify
    # the application-level contract (tz-aware datetimes) independently
    # of that SQLite storage limitation.
    TestingSessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(tmp_path: Path, db_session: Session) -> Generator[TestClient, None, None]:
    """A TestClient wired to the isolated `db_session` and a temp upload dir.

    Neither the real database nor the developer's real uploads directory is
    ever touched by API-level tests.
    """

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    def _override_get_upload_root() -> Path:
        return tmp_path / "uploads" / "digitizer"

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_upload_root] = _override_get_upload_root
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
