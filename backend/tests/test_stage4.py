"""Integration tests for Stage 4 — VPN-core wiring, quota enforcement, subscription.

All vpn-core functions are mocked — no real OpenVPN server required.
Covers:
- Quota exceeded → user disabled + admin data_used updated
- Expiry passed → user marked expired
- Counter reset handled without negative usage
- Admin quota exceeded blocks new user creation
- /sub/{token} returns 200 with valid config and 404 for invalid/revoked
- Revoking a subscription token immediately 404s the old link
- Server-config PUT only commits to DB when vpn-core's apply step succeeds
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.models.admin import Admin
from app.models.server_config import ServerConfig
from app.models.user import (
    DataLimitResetStrategy,
    User,
    UserStatus,
)
from app.utils.password import hash_password

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session():
    """Clean in-memory SQLite session, rolled back after each test."""
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
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    # Attach factory to session so scheduler tests can monkey-patch with it
    session.info["test_session_factory"] = session_factory
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session):
    """FastAPI TestClient using in-memory DB."""
    from app import create_app

    app = create_app()

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    # Disable scheduler startup for tests
    app.router.on_startup.clear()
    app.router.on_shutdown.clear()

    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def sudo_client(client, db_session):
    """TestClient pre-authenticated as the sudo admin."""
    from app.db.seed import seed_sudo_admin

    seed_sudo_admin(db_session)
    db_session.commit()

    resp = client.post("/api/admin/token", json={"username": "admin", "password": "admin"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


def _make_admin(db, username, is_sudo=False, data_limit=None, parent_admin_id=None):
    admin = Admin(
        username=username,
        hashed_password=hash_password("pass"),
        is_sudo=is_sudo,
        disabled=False,
        data_limit=data_limit,
        data_used=0,
        parent_admin_id=parent_admin_id,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def _make_user(db, admin_id, username, data_limit=None, data_used=0, status=UserStatus.ACTIVE):
    user = User(
        username=username,
        admin_id=admin_id,
        data_limit=data_limit,
        data_used=data_used,
        status=status,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _login(client, username, password="pass"):
    resp = client.post("/api/admin/token", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _patch_db(db_session):
    """Context manager that monkey-patches SessionLocal to use the test engine."""
    import app.db

    original = app.db.SessionLocal
    factory = db_session.info.get("test_session_factory")
    app.db.SessionLocal = factory
    return original


# ===========================================================================
# 1. User creation wired to vpn-core
# ===========================================================================


class TestCreateUserVPNCore:
    @patch("app.routers.users._create_client_cert")
    def test_create_user_calls_vpn_core(self, mock_create, sudo_client, db_session):
        mock_create.return_value = "ovpn-content-here"
        resp = sudo_client.post(
            "/api/users",
            json={"username": "vpn-user-1", "data_limit": 1024**3},
        )
        assert resp.status_code == 201
        mock_create.assert_called_once()
        data = resp.json()
        assert data["username"] == "vpn-user-1"
        assert data["common_name"] == "vpn-user-1"

    @patch("app.routers.users._create_client_cert")
    def test_cert_failure_no_db_row(self, mock_create, sudo_client, db_session):
        mock_create.side_effect = RuntimeError("easy-rsa failed")
        resp = sudo_client.post(
            "/api/users",
            json={"username": "fail-user", "data_limit": 1024},
        )
        assert resp.status_code == 500
        assert "certificate" in resp.json()["detail"].lower()
        # Verify no user was created in DB
        user = db_session.query(User).filter(User.username == "fail-user").first()
        assert user is None

    @patch("app.routers.users._create_client_cert")
    def test_cert_exists_no_db_row(self, mock_create, sudo_client, db_session):
        mock_create.side_effect = FileExistsError("already exists")
        resp = sudo_client.post(
            "/api/users",
            json={"username": "dup-cert", "data_limit": 1024},
        )
        assert resp.status_code == 409
        assert "certificate" in resp.json()["detail"].lower()


# ===========================================================================
# 2. Quota enforcement — admin quota exceeded blocks creation
# ===========================================================================


class TestAdminQuotaBlocksCreation:
    def test_sub_admin_over_quota_rejected(self, client, db_session):
        from app.db.seed import seed_sudo_admin
        seed_sudo_admin(db_session)
        db_session.commit()

        sudo = db_session.query(Admin).filter(Admin.is_sudo.is_(True)).first()
        _ = _make_admin(db_session, "quota_admin", data_limit=5 * 1024**3, parent_admin_id=sudo.id)
        headers = _login(client, "quota_admin")

        resp = client.post(
            "/api/users",
            json={"username": "big_user", "data_limit": 10 * 1024**3},
            headers=headers,
        )
        assert resp.status_code == 409
        assert "quota" in resp.json()["detail"].lower()


# ===========================================================================
# 3. Quota exceeded → user disabled + admin data_used updated
# ===========================================================================


class TestEnforceLimitsQuota:
    @patch("app.jobs.enforce_limits.kill_client_session")
    @patch("app.jobs.enforce_limits.disable_client")
    def test_data_limit_enforced(self, mock_disable, mock_kill, db_session):
        from app.jobs.enforce_limits import enforce_limits_job

        admin = _make_admin(db_session, "enf_admin", data_limit=10 * 1024**3)
        user = _make_user(
            db_session, admin.id, "over_user",
            data_limit=1024**3, data_used=2 * 1024**3,  # Over limit
        )
        user.common_name = "over_user"
        db_session.commit()

        original = _patch_db(db_session)
        try:
            enforce_limits_job()
        finally:
            import app.db
            app.db.SessionLocal = original

        db_session.expire_all()
        db_session.refresh(user)
        assert user.status == UserStatus.LIMITED
        mock_kill.assert_called()

    @patch("app.jobs.enforce_limits.kill_client_session")
    @patch("app.jobs.enforce_limits.disable_client")
    def test_admin_data_used_not_changed_by_enforce(self, mock_disable, mock_kill, db_session):
        """enforce_limits does NOT update admin.data_used — that's sync_usage's job."""
        from app.jobs.enforce_limits import enforce_limits_job

        admin = _make_admin(db_session, "admin2", data_limit=10 * 1024**3)
        _make_user(db_session, admin.id, "u1", data_limit=1024**3, data_used=2 * 1024**3)
        _make_user(db_session, admin.id, "u2", data_limit=1024**3, data_used=512 * 1024**2)
        db_session.commit()

        original = _patch_db(db_session)
        try:
            enforce_limits_job()
        finally:
            import app.db
            app.db.SessionLocal = original

        db_session.expire_all()
        db_session.refresh(admin)
        # enforce_limits only limits/disables — it does NOT recalculate admin.data_used
        # That's sync_usage's responsibility
        assert admin.data_used == 0  # unchanged by enforce_limits


# ===========================================================================
# 4. Expiry passed → user marked expired
# ===========================================================================


class TestEnforceLimitsExpiry:
    @patch("app.jobs.enforce_limits.kill_client_session")
    @patch("app.jobs.enforce_limits.disable_client")
    def test_expired_user_marked(self, mock_disable, mock_kill, db_session):
        from app.jobs.enforce_limits import enforce_limits_job

        admin = _make_admin(db_session, "exp_admin")
        user = _make_user(db_session, admin.id, "old_user")
        user.common_name = "old_user"
        user.expire_at = dt.datetime.now(dt.UTC) - dt.timedelta(hours=1)
        db_session.commit()

        original = _patch_db(db_session)
        try:
            enforce_limits_job()
        finally:
            import app.db
            app.db.SessionLocal = original

        db_session.expire_all()
        db_session.refresh(user)
        assert user.status == UserStatus.EXPIRED

    @patch("app.jobs.enforce_limits.kill_client_session")
    @patch("app.jobs.enforce_limits.disable_client")
    def test_active_user_not_affected(self, mock_disable, mock_kill, db_session):
        from app.jobs.enforce_limits import enforce_limits_job

        admin = _make_admin(db_session, "ok_admin")
        user = _make_user(db_session, admin.id, "ok_user")
        user.common_name = "ok_user"
        user.expire_at = dt.datetime.now(dt.UTC) + dt.timedelta(days=30)
        db_session.commit()

        original = _patch_db(db_session)
        try:
            enforce_limits_job()
        finally:
            import app.db
            app.db.SessionLocal = original

        db_session.expire_all()
        db_session.refresh(user)
        assert user.status == UserStatus.ACTIVE


# ===========================================================================
# 5. Usage accounting — baseline seeding, reconnect/restart, atomic updates
# ===========================================================================


class TestSyncUsageAccounting:
    def _sync_user(self, db_session, username, *runs):
        from app.jobs.sync_usage import sync_usage_job
        admin = _make_admin(db_session, f"sync_{username}")
        user = _make_user(db_session, admin.id, username)
        user.common_name = username
        user.data_used = 5000
        db_session.commit()
        original = _patch_db(db_session)
        try:
            with patch("app.jobs.sync_usage.get_live_status") as mock_status:
                for run in runs:
                    mock_status.return_value = [run]
                    sync_usage_job()
        finally:
            import app.db
            app.db.SessionLocal = original
        db_session.expire_all()
        db_session.refresh(user)
        return user

    @patch("app.jobs.sync_usage.get_live_status")
    def test_first_observe_seeds_baseline_no_double_count(self, mock_status, db_session):
        """A connected client's pre-existing session must NOT be re-counted
        after a backend restart (baseline is seeded instead)."""
        from app.jobs.sync_usage import sync_usage_job

        admin = _make_admin(db_session, "seed_admin")
        user = _make_user(db_session, admin.id, "seed_user")
        user.common_name = "seed_user"
        user.data_used = 5000
        db_session.commit()
        original = _patch_db(db_session)

        # Single poll of an already-running session (as seen right after a
        # backend restart): this seeds the baseline and counts nothing.
        mock_status.return_value = [
            {"common_name": "seed_user", "real_address": "1.2.3.4",
             "bytes_received": 3000, "bytes_sent": 2000, "connected_since": "2025-01-01"},
        ]
        sync_usage_job()

        import app.db
        app.db.SessionLocal = original

        db_session.expire_all()
        db_session.refresh(user)
        assert user.data_used == 5000  # no double-count of the 5000-byte session

    @patch("app.jobs.sync_usage.get_live_status")
    def test_deltas_accumulate_after_baseline(self, mock_status, db_session):
        """Only traffic observed AFTER the baseline is accumulated."""
        from app.jobs.sync_usage import sync_usage_job

        admin = _make_admin(db_session, "delta_admin")
        user = _make_user(db_session, admin.id, "delta_user")
        user.common_name = "delta_user"
        user.data_used = 5000
        db_session.commit()
        original = _patch_db(db_session)

        mock_status.return_value = [
            {"common_name": "delta_user", "real_address": "1.2.3.4",
             "bytes_received": 1000, "bytes_sent": 500, "connected_since": "2025-01-01"},
        ]
        sync_usage_job()  # seed baseline, counts nothing
        mock_status.return_value = [
            {"common_name": "delta_user", "real_address": "1.2.3.4",
             "bytes_received": 3500, "bytes_sent": 2500, "connected_since": "2025-01-01"},
        ]
        sync_usage_job()  # 5000 + 2500 + 2000 = 9500

        import app.db
        app.db.SessionLocal = original

        db_session.expire_all()
        db_session.refresh(user)
        assert user.data_used == 9500

    def test_reconnect_counts_full_new_session(self, db_session):
        """Counters going down (OpenVPN reconnect/restart) restart the
        session and the full new totals are counted."""
        user = self._sync_user(
            db_session, "reconnect_user",
            {"common_name": "reconnect_user", "real_address": "1.2.3.4",
             "bytes_received": 3000, "bytes_sent": 2000, "connected_since": "2025-01-01"},
            {"common_name": "reconnect_user", "real_address": "1.2.3.4",
             "bytes_received": 2500, "bytes_sent": 200, "connected_since": "2025-01-02"},
        )
        # seed run counts nothing; reconnect run counts 2500 + 200
        assert user.data_used == 5000 + 2700

    def test_session_change_detected_via_connected_since(self, db_session):
        """A reconnect whose new session already outgrew the old baseline is
        still counted in full (previously under-counted by the delta)."""
        user = self._sync_user(
            db_session, "sesschange_user",
            {"common_name": "sesschange_user", "real_address": "1.2.3.4",
             "bytes_received": 100, "bytes_sent": 50, "connected_since": "2025-01-01"},
            {"common_name": "sesschange_user", "real_address": "1.2.3.4",
             "bytes_received": 5000, "bytes_sent": 3000, "connected_since": "2025-01-02"},
        )
        # second poll: new session (timestamp differs) → count full 8000,
        # NOT only 8000 - 150
        assert user.data_used == 5000 + 8000

    def test_reconnect_after_disconnect_counts_new_session(self, db_session):
        """A disconnect+reconnect between polls must NOT lose the new session.

        The snapshot lives in the DB (not process memory) and is never
        cleared on disconnect, so the fresh session's full counters are
        counted instead of being re-baselined (which would count nothing).
        """
        from app.jobs.sync_usage import sync_usage_job

        admin = _make_admin(db_session, "re_dc_admin")
        user = _make_user(db_session, admin.id, "re_dc_user")
        user.common_name = "re_dc_user"
        user.data_used = 5000
        db_session.commit()
        original = _patch_db(db_session)
        try:
            with patch("app.jobs.sync_usage.get_live_status") as mock_status:
                # Session A — seed baseline, then count a delta
                mock_status.return_value = [
                    {"common_name": "re_dc_user", "real_address": "1.2.3.4",
                     "bytes_received": 3000, "bytes_sent": 2000,
                     "connected_since": "2025-01-01"},
                ]
                sync_usage_job()  # seed, counts nothing
                mock_status.return_value = [
                    {"common_name": "re_dc_user", "real_address": "1.2.3.4",
                     "bytes_received": 3500, "bytes_sent": 2500,
                     "connected_since": "2025-01-01"},
                ]
                sync_usage_job()  # delta = 1000 -> 6000

                # Client disconnects — the snapshot must survive.
                mock_status.return_value = []
                sync_usage_job()

                # Reconnect — fresh per-session counters (lower than the
                # snapshot): must be counted as a full new session.
                mock_status.return_value = [
                    {"common_name": "re_dc_user", "real_address": "1.2.3.4",
                     "bytes_received": 500, "bytes_sent": 300,
                     "connected_since": "2025-01-02"},
                ]
                sync_usage_job()  # full 800 -> 6800
        finally:
            import app.db
            app.db.SessionLocal = original

        db_session.expire_all()
        db_session.refresh(user)
        assert user.data_used == 5000 + 1000 + 800

    def test_atomic_update_not_clobbered_by_reset(self, db_session):
        """A usage reset committed between the delta read and the write must
        not be resurrected: data_used is updated atomically in SQL."""
        from app.jobs.sync_usage import sync_usage_job

        admin = _make_admin(db_session, "atomic_admin")
        user = _make_user(db_session, admin.id, "atomic_user")
        user.common_name = "atomic_user"
        user.data_used = 5000
        db_session.commit()
        original = _patch_db(db_session)
        try:
            with patch("app.jobs.sync_usage.get_live_status") as mock_status:
                mock_status.return_value = [
                    {"common_name": "atomic_user", "real_address": "1.2.3.4",
                     "bytes_received": 1000, "bytes_sent": 500, "connected_since": "2025-01-01"},
                ]
                sync_usage_job()  # seed baseline, counts nothing
        finally:
            import app.db
            app.db.SessionLocal = original

        # Concurrent reset-usage via a separate session while the client is
        # still connected.
        factory = db_session.info["test_session_factory"]
        other = factory()
        try:
            u = other.query(User).filter(User.username == "atomic_user").first()
            u.data_used = 0
            other.commit()
        finally:
            other.close()

        original = _patch_db(db_session)
        try:
            with patch("app.jobs.sync_usage.get_live_status") as mock_status:
                mock_status.return_value = [
                    {"common_name": "atomic_user", "real_address": "1.2.3.4",
                     "bytes_received": 1500, "bytes_sent": 900, "connected_since": "2025-01-01"},
                ]
                sync_usage_job()  # delta = (1500-1000) + (900-500) = 900
        finally:
            import app.db
            app.db.SessionLocal = original

        db_session.expire_all()
        db_session.refresh(user)
        # Atomic `data_used = data_used + delta` is applied relative to the
        # CURRENT committed value (0 after the reset), so the reset survives
        # and only the new delta is accumulated.
        assert user.data_used == 0 + 900


# ===========================================================================
# 6. /sub/{token} — public subscription endpoint
# ===========================================================================


class TestSubscriptionEndpoint:
    @patch("app.routers.subscription.generate_ovpn_file")
    def test_valid_token_returns_landing_page(self, mock_ovpn, client, db_session):
        from app.db.seed import seed_default_server_config

        mock_ovpn.return_value = "client\ndev tun\nproto udp\n"

        admin = _make_admin(db_session, "sub_admin")
        user = _make_user(db_session, admin.id, "sub_user")
        user.common_name = "sub_user"
        db_session.commit()

        seed_default_server_config(db_session)
        cfg = db_session.query(ServerConfig).first()
        cfg.public_host = "vpn.example.com"
        cfg.port = 1194
        db_session.commit()

        resp = client.get(f"/sub/{user.subscription_token}")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "sub_user" in resp.text
        assert "Download Config" in resp.text

    @patch("app.routers.subscription.generate_ovpn_file")
    def test_subscription_links_include_base_path(
        self, mock_ovpn, client, sudo_client, db_session
    ):
        """With APP_BASE_PATH set, subscription URLs point at the prefix."""
        from app import config as app_config
        from app.db.seed import seed_default_server_config

        mock_ovpn.return_value = "client\ndev tun\nproto udp\n"

        admin = _make_admin(db_session, "bp_admin")
        user = _make_user(db_session, admin.id, "bp_user")
        user.common_name = "bp_user"
        db_session.commit()

        seed_default_server_config(db_session)
        cfg = db_session.query(ServerConfig).first()
        cfg.public_host = "vpn.example.com"
        cfg.port = 1194
        cfg.subscription_url_prefix = ""
        db_session.commit()

        token = user.subscription_token
        old = app_config.APP_BASE_PATH
        app_config.APP_BASE_PATH = "/dashboard"
        try:
            # Landing page download link points at the prefixed path
            resp = client.get(f"/sub/{token}")
            assert resp.status_code == 200
            assert f"/dashboard/sub/{token}/download" in resp.text

            # The admin-facing subscription URL includes the prefix too
            resp = sudo_client.get(f"/api/users/{user.username}/subscription-url")
            assert resp.status_code == 200
            url = resp.json()["subscription_url"]
            assert f"http://testserver/dashboard/sub/{token}" == url
        finally:
            app_config.APP_BASE_PATH = old

    @patch("app.routers.subscription.generate_ovpn_file")
    def test_valid_token_returns_ovpn_on_download(self, mock_ovpn, client, db_session):
        from app.db.seed import seed_default_server_config

        mock_ovpn.return_value = "client\ndev tun\nproto udp\n"

        admin = _make_admin(db_session, "dl_admin")
        user = _make_user(db_session, admin.id, "dl_user")
        user.common_name = "dl_user"
        db_session.commit()

        seed_default_server_config(db_session)
        cfg = db_session.query(ServerConfig).first()
        cfg.public_host = "vpn.example.com"
        cfg.port = 1194
        db_session.commit()

        resp = client.get(f"/sub/{user.subscription_token}/download")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/x-openvpn-profile"
        assert "dl_user" in resp.headers.get("content-disposition", "")

    @patch("app.routers.subscription.generate_ovpn_file")
    def test_sub_download_uses_tunnel_host_when_set(self, mock_ovpn, client, db_session):
        from app.db.seed import seed_default_server_config

        mock_ovpn.return_value = "client\ndev tun\nproto udp\n"

        admin = _make_admin(db_session, "sub_tun_admin")
        user = _make_user(db_session, admin.id, "sub_tun_user")
        user.common_name = "sub_tun_user"
        db_session.commit()

        seed_default_server_config(db_session)
        cfg = db_session.query(ServerConfig).first()
        cfg.public_host = "vpn.example.com"
        cfg.tunnel_host = "tunnel.example.com"
        db_session.commit()

        resp = client.get(f"/sub/{user.subscription_token}/download")
        assert resp.status_code == 200
        mock_ovpn.assert_called_once()
        assert mock_ovpn.call_args.kwargs["public_ip"] == "tunnel.example.com"

    def test_invalid_token_returns_404(self, client, db_session):
        resp = client.get("/sub/this_token_does_not_exist")
        assert resp.status_code == 404

    def test_invalid_token_download_returns_404(self, client, db_session):
        resp = client.get("/sub/this_token_does_not_exist/download")
        assert resp.status_code == 404

    def test_revoked_token_returns_404(self, client, db_session):
        admin = _make_admin(db_session, "rev_admin")
        user = _make_user(db_session, admin.id, "rev_user", status=UserStatus.DISABLED)
        user.revoked = True
        db_session.commit()

        resp = client.get(f"/sub/{user.subscription_token}")
        assert resp.status_code == 404

    @patch("app.routers.subscription.generate_ovpn_file")
    def test_no_auth_header_required(self, mock_ovpn, client, db_session):
        mock_ovpn.return_value = "ovpn-content"

        admin = _make_admin(db_session, "pub_admin")
        user = _make_user(db_session, admin.id, "pub_user")
        user.common_name = "pub_user"
        db_session.commit()

        resp = client.get(f"/sub/{user.subscription_token}", headers={})
        assert resp.status_code != 401

    @patch("app.routers.subscription.generate_ovpn_file")
    def test_revoke_immediately_404s_old_token(self, mock_ovpn, client, db_session):
        mock_ovpn.return_value = "ovpn-content"

        admin = _make_admin(db_session, "tok_admin")
        user = _make_user(db_session, admin.id, "tok_user")
        user.common_name = "tok_user"
        db_session.commit()

        old_token = user.subscription_token

        headers = _login(client, "tok_admin")
        resp = client.post(
            f"/api/users/{user.username}/subscription/revoke",
            headers=headers,
        )
        assert resp.status_code == 200
        new_user = resp.json()
        assert new_user["username"] == "tok_user"

        resp = client.get(f"/sub/{old_token}")
        assert resp.status_code == 404

        resp = client.get(f"/sub/{old_token}/download")
        assert resp.status_code == 404


# ===========================================================================
# 7. Rate limiting on /sub/{token}
# ===========================================================================


class TestSubscriptionRateLimit:
    @patch("app.routers.subscription.generate_ovpn_file")
    def test_rate_limit_enforced(self, mock_ovpn, client, db_session):
        from app.services.rate_limiter import subscription_rate_limiter

        mock_ovpn.return_value = "ovpn-content"

        # Reset rate limiter state
        subscription_rate_limiter._hits.clear()
        subscription_rate_limiter.max_requests = 3

        admin = _make_admin(db_session, "rl_admin")
        user = _make_user(db_session, admin.id, "rl_user")
        user.common_name = "rl_user"
        db_session.commit()

        # Make 3 requests (should succeed)
        for _ in range(3):
            resp = client.get(f"/sub/{user.subscription_token}", headers={})
            assert resp.status_code == 200

        # 4th request should be rate limited
        resp = client.get(f"/sub/{user.subscription_token}", headers={})
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

        # Reset for other tests
        subscription_rate_limiter.max_requests = 10


# ===========================================================================
# 8. Server config PUT only commits when vpn-core succeeds
# ===========================================================================


class TestServerConfigApply:
    def test_get_server_config(self, sudo_client, db_session):
        from app.db.seed import seed_default_server_config
        seed_default_server_config(db_session)
        db_session.commit()

        resp = sudo_client.get("/api/settings/server-config")
        assert resp.status_code == 200
        assert resp.json()["protocol"] == "udp"
        assert resp.json()["port"] == 1194

    @patch("app.routers.settings._apply_server_config")
    def test_apply_success_commits_db(self, mock_apply, sudo_client, db_session):
        from app.db.seed import seed_default_server_config
        seed_default_server_config(db_session)
        db_session.commit()

        mock_apply.return_value = True

        resp = sudo_client.put(
            "/api/settings/server-config",
            json={"port": 11940},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # Verify DB was updated
        cfg = db_session.query(ServerConfig).first()
        assert cfg.port == 11940

    @patch("app.routers.settings._apply_server_config")
    def test_apply_failure_does_not_commit(self, mock_apply, sudo_client, db_session):
        from app.db.seed import seed_default_server_config
        seed_default_server_config(db_session)
        db_session.commit()

        original_port = db_session.query(ServerConfig).first().port

        mock_apply.return_value = False

        resp = sudo_client.put(
            "/api/settings/server-config",
            json={"port": 11940},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is False

        # Verify DB was NOT updated
        cfg = db_session.query(ServerConfig).first()
        assert cfg.port == original_port

    @patch("app.routers.settings._apply_server_config")
    def test_apply_exception_does_not_commit(self, mock_apply, sudo_client, db_session):
        from app.db.seed import seed_default_server_config
        seed_default_server_config(db_session)
        db_session.commit()

        original_port = db_session.query(ServerConfig).first().port

        mock_apply.side_effect = RuntimeError("systemctl not found")

        resp = sudo_client.put(
            "/api/settings/server-config",
            json={"port": 11940},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is False
        assert "systemctl" in resp.json()["message"]

        cfg = db_session.query(ServerConfig).first()
        assert cfg.port == original_port

    @patch("app.routers.settings._apply_server_config")
    def test_redistribution_fields_warning(self, mock_apply, sudo_client, db_session):
        from app.db.seed import seed_default_server_config
        seed_default_server_config(db_session)
        db_session.commit()

        mock_apply.return_value = True

        resp = sudo_client.put(
            "/api/settings/server-config",
            json={"protocol": "tcp"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["requires_redownload"] is True
        assert "protocol" in data["requires_redownload_fields"]

    @patch("app.routers.settings._apply_server_config")
    def test_non_redistribution_fields_no_warning(self, mock_apply, sudo_client, db_session):
        from app.db.seed import seed_default_server_config
        seed_default_server_config(db_session)
        db_session.commit()

        mock_apply.return_value = True

        resp = sudo_client.put(
            "/api/settings/server-config",
            json={"dns_preset": "google"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["requires_redownload"] is False
        assert data["requires_redownload_fields"] == []

    @patch("app.routers.settings._apply_server_config")
    def test_tunnel_host_only_change_commits_without_restart(self, mock_apply, sudo_client, db_session):
        from app.db.seed import seed_default_server_config
        seed_default_server_config(db_session)
        db_session.commit()

        resp = sudo_client.put(
            "/api/settings/server-config",
            json={"tunnel_host": "tunnel.example.com"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        # Tunnel change is client-facing — no OpenVPN restart, but clients
        # should redownload to pick up the new remote endpoint.
        assert data["requires_redownload"] is True
        assert "tunnel_host" in data["requires_redownload_fields"]
        mock_apply.assert_not_called()

        cfg = db_session.query(ServerConfig).first()
        db_session.refresh(cfg)
        assert cfg.tunnel_host == "tunnel.example.com"

    @patch("app.routers.settings._apply_server_config")
    def test_tunnel_host_cleared_without_restart(self, mock_apply, sudo_client, db_session):
        from app.db.seed import seed_default_server_config
        seed_default_server_config(db_session)
        cfg = db_session.query(ServerConfig).first()
        cfg.tunnel_host = "tunnel.example.com"
        db_session.commit()

        resp = sudo_client.put(
            "/api/settings/server-config",
            json={"tunnel_host": ""},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        mock_apply.assert_not_called()

        db_session.refresh(cfg)
        assert cfg.tunnel_host == ""


# ===========================================================================
# 9. Disable / Enable user
# ===========================================================================


class TestDisableEnable:
    @patch("app.routers.users._kill_client_session")
    @patch("app.routers.users._disable_client")
    def test_disable_user(self, mock_disable, mock_kill, sudo_client, db_session):
        admin = db_session.query(Admin).filter(Admin.is_sudo.is_(True)).first()
        user = _make_user(db_session, admin.id, "dis_user")
        user.common_name = "dis_user"
        db_session.commit()

        resp = sudo_client.post(f"/api/users/{user.username}/disable")
        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"
        mock_kill.assert_called()

    @patch("app.routers.users._enable_client")
    def test_enable_user(self, mock_enable, sudo_client, db_session):
        admin = db_session.query(Admin).filter(Admin.is_sudo.is_(True)).first()
        user = _make_user(db_session, admin.id, "ena_user", status=UserStatus.DISABLED)
        user.common_name = "ena_user"
        db_session.commit()

        resp = sudo_client.post(f"/api/users/{user.username}/enable")
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"
        mock_enable.assert_called()


# ===========================================================================
# 10. Reset usage
# ===========================================================================


class TestResetUsage:
    def test_reset_usage_zeroes_data_used(self, sudo_client, db_session):
        admin = db_session.query(Admin).filter(Admin.is_sudo.is_(True)).first()
        user = _make_user(db_session, admin.id, "reset_u", data_used=5000)
        admin.data_used = 5000
        db_session.commit()

        resp = sudo_client.post(f"/api/users/{user.username}/reset-usage")
        assert resp.status_code == 200
        assert resp.json()["data_used"] == 0

        db_session.refresh(admin)
        assert admin.data_used == 0


# ===========================================================================
# 11. Periodic quota reset
# ===========================================================================


class TestPeriodicReset:
    def test_daily_reset_re_enables_limited_user(self, db_session):
        from app.jobs.reset_periodic_limits import reset_periodic_limits_job

        admin = _make_admin(db_session, "pr_admin")
        user = _make_user(
            db_session, admin.id, "daily_u",
            data_limit=1024, data_used=2048,
            status=UserStatus.LIMITED,
        )
        user.data_limit_reset_strategy = DataLimitResetStrategy.DAILY
        user.last_reset_at = dt.datetime.now(dt.UTC) - dt.timedelta(days=2)
        db_session.commit()

        original = _patch_db(db_session)
        try:
            reset_periodic_limits_job()
        finally:
            import app.db
            app.db.SessionLocal = original

        db_session.expire_all()
        db_session.refresh(user)
        assert user.data_used == 0
        assert user.status == UserStatus.ACTIVE

    def test_expired_user_not_reset(self, db_session):
        from app.jobs.reset_periodic_limits import reset_periodic_limits_job

        admin = _make_admin(db_session, "pr_admin2")
        user = _make_user(
            db_session, admin.id, "exp_u",
            data_limit=1024, data_used=2048,
            status=UserStatus.EXPIRED,
        )
        user.data_limit_reset_strategy = DataLimitResetStrategy.DAILY
        db_session.commit()

        original = _patch_db(db_session)
        try:
            reset_periodic_limits_job()
        finally:
            import app.db
            app.db.SessionLocal = original

        db_session.expire_all()
        db_session.refresh(user)
        assert user.data_used == 2048  # Should NOT be reset
        assert user.status == UserStatus.EXPIRED


# ===========================================================================
# 12. Subscription URL endpoint
# ===========================================================================


class TestSubscriptionURL:
    def test_get_subscription_url(self, sudo_client, db_session):
        from app.db.seed import seed_default_server_config
        seed_default_server_config(db_session)
        cfg = db_session.query(ServerConfig).first()
        cfg.subscription_url_prefix = "https://panel.example.com"
        db_session.commit()

        admin = db_session.query(Admin).filter(Admin.is_sudo.is_(True)).first()
        user = _make_user(db_session, admin.id, "url_u")
        db_session.commit()

        resp = sudo_client.get(f"/api/users/{user.username}/subscription-url")
        assert resp.status_code == 200
        assert "https://panel.example.com/sub/" in resp.json()["subscription_url"]

    def test_no_prefix_derives_from_request(self, sudo_client, db_session):
        from app.db.seed import seed_default_server_config
        seed_default_server_config(db_session)
        db_session.commit()

        admin = db_session.query(Admin).filter(Admin.is_sudo.is_(True)).first()
        user = _make_user(db_session, admin.id, "noprefix_u")
        db_session.commit()

        resp = sudo_client.get(f"/api/users/{user.username}/subscription-url")
        assert resp.status_code == 200
        url = resp.json()["subscription_url"]
        assert url.startswith("http://")
        assert f"/sub/{user.subscription_token}" in url


# ===========================================================================
# 13. Config download endpoint
# ===========================================================================


class TestConfigDownload:
    @patch("app.routers.users._generate_ovpn_file")
    def test_get_config_returns_ovpn(self, mock_ovpn, sudo_client, db_session):
        mock_ovpn.return_value = "client\ndev tun\nproto udp\n"

        admin = db_session.query(Admin).filter(Admin.is_sudo.is_(True)).first()
        user = _make_user(db_session, admin.id, "cfg_u")
        user.common_name = "cfg_u"
        db_session.commit()

        resp = sudo_client.get(f"/api/users/{user.username}/config")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/x-openvpn-profile"

    @patch("app.routers.users._generate_ovpn_file")
    def test_config_uses_tunnel_host_when_set(self, mock_ovpn, sudo_client, db_session):
        from app.db.seed import seed_default_server_config

        mock_ovpn.return_value = "client\ndev tun\nproto udp\n"

        seed_default_server_config(db_session)
        cfg = db_session.query(ServerConfig).first()
        cfg.public_host = "vpn.example.com"
        cfg.tunnel_host = "tunnel.example.com"
        db_session.commit()

        admin = db_session.query(Admin).filter(Admin.is_sudo.is_(True)).first()
        user = _make_user(db_session, admin.id, "cfg_tun")
        user.common_name = "cfg_tun"
        db_session.commit()

        resp = sudo_client.get(f"/api/users/{user.username}/config")
        assert resp.status_code == 200
        mock_ovpn.assert_called_once()
        assert mock_ovpn.call_args.kwargs["public_ip"] == "tunnel.example.com"

    @patch("app.routers.users._generate_ovpn_file")
    def test_config_falls_back_to_public_host_without_tunnel(self, mock_ovpn, sudo_client, db_session):
        from app.db.seed import seed_default_server_config

        mock_ovpn.return_value = "client\ndev tun\nproto udp\n"

        seed_default_server_config(db_session)
        cfg = db_session.query(ServerConfig).first()
        cfg.public_host = "vpn.example.com"
        cfg.tunnel_host = ""
        db_session.commit()

        admin = db_session.query(Admin).filter(Admin.is_sudo.is_(True)).first()
        user = _make_user(db_session, admin.id, "cfg_notun")
        user.common_name = "cfg_notun"
        db_session.commit()

        resp = sudo_client.get(f"/api/users/{user.username}/config")
        assert resp.status_code == 200
        mock_ovpn.assert_called_once()
        assert mock_ovpn.call_args.kwargs["public_ip"] == "vpn.example.com"

    def test_revoked_user_config_returns_410(self, sudo_client, db_session):
        admin = db_session.query(Admin).filter(Admin.is_sudo.is_(True)).first()
        user = _make_user(db_session, admin.id, "rev_cfg_u")
        user.revoked = True
        db_session.commit()

        resp = sudo_client.get(f"/api/users/{user.username}/config")
        assert resp.status_code == 410
