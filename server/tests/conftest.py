from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registers all models on Base.metadata)
from app.db.base import Base


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
