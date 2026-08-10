"""Test fixtures — provides an in-memory SQLite database and a FastAPI test client."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def db_session():
    """Yield a clean in-memory SQLite session, rolled back after each test."""
    from app.db import Base
    from app.models import Admin, AdminLog, ServerConfig, UsageLog, User  # noqa: F401
    from app.models.jwt import JWTSecret  # noqa: F401

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

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


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset global rate limiters between tests.

    Both limiters are module-level singletons shared across the whole
    test session; without clearing them, earlier tests leak hits into
    later ones and cause spurious 429s (e.g. the /sub/{token} tests in
    different files hitting the same in-memory counter).
    """
    yield
    try:
        from app.routers.auth import _login_rate_limiter
        _login_rate_limiter._hits.clear()
    except ImportError:
        pass
    try:
        from app.services.rate_limiter import subscription_rate_limiter
        subscription_rate_limiter._hits.clear()
    except ImportError:
        pass


@pytest.fixture()
def client(db_session):
    """Yield a FastAPI TestClient that uses the same in-memory DB as db_session."""
    mock_scheduler = MagicMock()

    with patch("app.db.SessionLocal", return_value=db_session), \
         patch("app.jobs.register_jobs"), \
         patch("app.jobs.scheduler", mock_scheduler):
        from app import create_app
        from app.db import get_db

        app = create_app()

        def _override_get_db():
            try:
                yield db_session
            finally:
                pass

        app.dependency_overrides[get_db] = _override_get_db

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

        app.dependency_overrides.clear()


@pytest.fixture()
def sudo_client(client, db_session):
    """Return a TestClient pre-authenticated as the sudo admin."""
    from app.db.seed import seed_sudo_admin

    seed_sudo_admin(db_session)
    db_session.commit()

    resp = client.post("/api/admin/token", json={"username": "admin", "password": "admin"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
