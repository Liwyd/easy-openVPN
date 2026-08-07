"""Test fixtures — provides an in-memory SQLite database for each test."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Admin, AdminLog, ServerConfig, UsageLog, User  # noqa: F401 — ensure all models are registered


@pytest.fixture()
def db_session():
    """Yield a clean in-memory SQLite session, rolled back after each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    # Enable SQLite foreign key enforcement so ON DELETE CASCADE/RESTRICT works.
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
