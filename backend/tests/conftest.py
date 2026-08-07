"""Test fixtures — provides an in-memory SQLite database and a FastAPI test client."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.models import Admin, AdminLog, ServerConfig, UsageLog, User  # noqa: F401 — ensure all models are registered
from app.models.jwt import JWTSecret  # noqa: F401 — ensure JWT model is registered


@pytest.fixture()
def db_session():
    """Yield a clean in-memory SQLite session, rolled back after each test.

    Uses StaticPool so all connections hit the same in-memory database.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Enable SQLite foreign key enforcement so ON DELETE CASCADE/RESTRICT works.
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(bind=engine)
    session = test_session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session):
    """Yield a FastAPI TestClient that uses the same in-memory DB as db_session."""
    from app import create_app

    app = create_app()

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def sudo_client(client, db_session):
    """Return a TestClient pre-authenticated as the sudo admin."""
    from app.db.seed import seed_sudo_admin

    seed_sudo_admin(db_session)
    db_session.commit()

    # Login as the sudo admin to get a real JWT token.
    resp = client.post("/api/admin/token", json={"username": "admin", "password": "admin"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
