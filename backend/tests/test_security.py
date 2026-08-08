"""Tests for security hardening — rate limiting, input validation, admin isolation,
CORS, password leak prevention, job concurrency guards.

Covers every bug class identified in the Stage 11 hardening pass.
"""

from __future__ import annotations

import datetime as dt
import threading
import time
from unittest.mock import patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.seed import seed_sudo_admin
from app.models.admin import Admin
from app.models.user import User, UserStatus
from app.services.rate_limiter import SlidingWindowRateLimiter
from app.utils.password import hash_password
from app.utils.validation import (
    validate_positive_int,
    validate_sane_datetime,
    validate_time_window,
    validate_username,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_admin(db, username, password="pass", is_sudo=False, data_limit=None, parent_admin_id=None):
    admin = Admin(
        username=username,
        hashed_password=hash_password(password),
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


def _login(client, username, password="pass"):
    resp = client.post("/api/admin/token", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _get_sudo(db):
    existing = db.query(Admin).filter(Admin.is_sudo.is_(True)).first()
    if existing:
        return existing
    seed_sudo_admin(db)
    db.commit()
    return db.query(Admin).filter(Admin.is_sudo.is_(True)).first()


# ===========================================================================
# 1. Rate Limiting
# ===========================================================================

class TestLoginRateLimiting:
    def test_rate_limiter_basic(self):
        limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60)
        assert not limiter.is_rate_limited("1.2.3.4")
        assert not limiter.is_rate_limited("1.2.3.4")
        assert not limiter.is_rate_limited("1.2.3.4")
        assert limiter.is_rate_limited("1.2.3.4")

    def test_rate_limiter_different_ips_independent(self):
        limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60)
        assert not limiter.is_rate_limited("1.1.1.1")
        assert not limiter.is_rate_limited("1.1.1.1")
        assert limiter.is_rate_limited("1.1.1.1")
        # Different IP should not be affected
        assert not limiter.is_rate_limited("2.2.2.2")

    def test_rate_limiter_retry_after(self):
        limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)
        limiter.is_rate_limited("1.2.3.4")
        retry = limiter.retry_after("1.2.3.4")
        assert retry >= 1
        assert retry <= 61

    def test_login_returns_429_after_5_failures(self, client, db_session):
        _create_admin(db_session, "rateuser", "correct")

        # Make 5 failed login attempts
        for _ in range(5):
            client.post(
                "/api/admin/token",
                json={"username": "rateuser", "password": "wrong"},
            )

        # 6th attempt should be rate-limited
        resp = client.post(
            "/api/admin/token",
            json={"username": "rateuser", "password": "wrong"},
        )
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

    def test_successful_login_does_not_increment_counter(self, client, db_session):
        _create_admin(db_session, "okuser", "goodpass")

        # 5 successful logins should not trigger rate limit
        for _ in range(5):
            resp = client.post(
                "/api/admin/token",
                json={"username": "okuser", "password": "goodpass"},
            )
            assert resp.status_code == 200

    def test_failed_logins_different_users_same_ip(self, client, db_session):
        """Rate limit is per-IP, not per-user."""
        _create_admin(db_session, "user_a", "pass_a")
        _create_admin(db_session, "user_b", "pass_b")

        for _ in range(3):
            client.post("/api/admin/token", json={"username": "user_a", "password": "wrong"})
            client.post("/api/admin/token", json={"username": "user_b", "password": "wrong"})

        # Total 6 failures from same IP — should be rate limited
        resp = client.post(
            "/api/admin/token",
            json={"username": "user_a", "password": "wrong"},
        )
        assert resp.status_code == 429


# ===========================================================================
# 2. Username Validation
# ===========================================================================

class TestUsernameValidation:
    def test_valid_usernames(self):
        validate_username("alice")
        validate_username("user-01")
        validate_username("admin_user")
        validate_username("A1b2C3")

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            validate_username("")

    def test_rejects_spaces(self):
        with pytest.raises(ValueError):
            validate_username("user name")

    def test_rejects_path_traversal(self):
        with pytest.raises(ValueError):
            validate_username("../../../etc/passwd")

    def test_rejects_backslash_traversal(self):
        with pytest.raises(ValueError):
            validate_username("..\\..\\windows\\system32")

    def test_rejects_special_chars(self):
        with pytest.raises(ValueError):
            validate_username("user@domain.com")
        with pytest.raises(ValueError):
            validate_username("user;rm -rf /")
        with pytest.raises(ValueError):
            validate_username("user`whoami`")
        with pytest.raises(ValueError):
            validate_username("${HOME}")

    def test_rejects_too_long(self):
        with pytest.raises(ValueError):
            validate_username("a" * 65)

    def test_allows_max_length(self):
        validate_username("a" * 64)

    def test_rejects_dot(self):
        with pytest.raises(ValueError):
            validate_username(".")

    def test_rejects_double_dot(self):
        with pytest.raises(ValueError):
            validate_username("..")

    def test_user_create_rejects_unsafe_username(self, sudo_client):
        resp = sudo_client.post(
            "/api/users",
            json={"username": "../../../etc", "data_limit": 1024},
        )
        assert resp.status_code == 422

    def test_user_create_rejects_special_chars(self, sudo_client):
        resp = sudo_client.post(
            "/api/users",
            json={"username": "user@domain", "data_limit": 1024},
        )
        assert resp.status_code == 422

    def test_admin_create_rejects_unsafe_username(self, sudo_client):
        resp = sudo_client.post(
            "/api/admins",
            json={"username": "user;rm", "password": "pass", "data_limit": 1024},
        )
        assert resp.status_code == 422


# ===========================================================================
# 3. Admin Isolation — non-sudo cannot access other admin's resources
# ===========================================================================

class TestAdminIsolation:
    def test_sub_admin_cannot_list_other_admin_users(self, client, db_session):
        sudo = _get_sudo(db_session)
        admin1 = _create_admin(db_session, "iso1", data_limit=10 * 1024**3, parent_admin_id=sudo.id)
        admin2 = _create_admin(db_session, "iso2", data_limit=10 * 1024**3, parent_admin_id=sudo.id)

        # Create user under admin1 via sudo
        user = User(username="secret_u", admin_id=admin1.id, data_used=0)
        db_session.add(user)
        db_session.commit()

        # admin2 tries to list — should not see admin1's users
        headers2 = _login(client, "iso2")
        resp = client.get("/api/users", headers=headers2)
        assert resp.status_code == 200
        usernames = [u["username"] for u in resp.json()]
        assert "secret_u" not in usernames

    def test_sub_admin_cannot_get_other_admin_user(self, client, db_session):
        sudo = _get_sudo(db_session)
        admin1 = _create_admin(db_session, "iso_a", data_limit=10 * 1024**3, parent_admin_id=sudo.id)
        admin2 = _create_admin(db_session, "iso_b", data_limit=10 * 1024**3, parent_admin_id=sudo.id)

        user = User(username="target_u", admin_id=admin1.id, data_used=0)
        db_session.add(user)
        db_session.commit()

        headers2 = _login(client, "iso_b")
        resp = client.get("/api/users/target_u", headers=headers2)
        assert resp.status_code == 404  # Not 403 (no existence leak)

    def test_sub_admin_cannot_update_other_admin_user(self, client, db_session):
        sudo = _get_sudo(db_session)
        admin1 = _create_admin(db_session, "iso_c", data_limit=10 * 1024**3, parent_admin_id=sudo.id)
        admin2 = _create_admin(db_session, "iso_d", data_limit=10 * 1024**3, parent_admin_id=sudo.id)

        user = User(username="protected_u", admin_id=admin1.id, data_used=0)
        db_session.add(user)
        db_session.commit()

        headers2 = _login(client, "iso_d")
        resp = client.put(
            "/api/users/protected_u",
            json={"data_limit": 999},
            headers=headers2,
        )
        assert resp.status_code == 404

    def test_sub_admin_cannot_delete_other_admin_user(self, client, db_session):
        sudo = _get_sudo(db_session)
        admin1 = _create_admin(db_session, "iso_e", data_limit=10 * 1024**3, parent_admin_id=sudo.id)
        admin2 = _create_admin(db_session, "iso_f", data_limit=10 * 1024**3, parent_admin_id=sudo.id)

        user = User(username="safe_u", admin_id=admin1.id, data_used=0)
        db_session.add(user)
        db_session.commit()

        headers2 = _login(client, "iso_f")
        resp = client.delete("/api/users/safe_u", headers=headers2)
        assert resp.status_code == 404

    def test_sub_admin_cannot_download_other_admin_config(self, client, db_session):
        sudo = _get_sudo(db_session)
        admin1 = _create_admin(db_session, "iso_g", data_limit=10 * 1024**3, parent_admin_id=sudo.id)
        admin2 = _create_admin(db_session, "iso_h", data_limit=10 * 1024**3, parent_admin_id=sudo.id)

        user = User(username="locked_u", admin_id=admin1.id, data_used=0)
        db_session.add(user)
        db_session.commit()

        headers2 = _login(client, "iso_h")
        resp = client.get("/api/users/locked_u/config", headers=headers2)
        assert resp.status_code == 404

    def test_non_sudo_cannot_create_admin(self, client, db_session):
        sudo = _get_sudo(db_session)
        sub = _create_admin(db_session, "sub_nocreate", data_limit=5 * 1024**3, parent_admin_id=sudo.id)
        headers = _login(client, "sub_nocreate")

        resp = client.post(
            "/api/admins",
            json={"username": "newadmin", "password": "pass", "data_limit": 1024},
            headers=headers,
        )
        assert resp.status_code == 403

    def test_non_sudo_cannot_access_settings(self, client, db_session):
        sudo = _get_sudo(db_session)
        sub = _create_admin(db_session, "sub_nosettings", data_limit=5 * 1024**3, parent_admin_id=sudo.id)
        headers = _login(client, "sub_nosettings")

        resp = client.get("/api/settings/server-config", headers=headers)
        assert resp.status_code == 403


# ===========================================================================
# 4. Subscription Endpoint Security
# ===========================================================================

class TestSubscriptionEndpointSecurity:
    def test_disabled_user_returns_404(self, sudo_client, db_session):
        """Disabled users' subscription links should return 404."""
        # Create a user with a known subscription token
        user = User(
            username="subtest",
            admin_id=1,
            subscription_token="test-token-123",
            status=UserStatus.DISABLED,
            data_used=0,
        )
        db_session.add(user)
        db_session.commit()

        resp = sudo_client.get("/sub/test-token-123")
        assert resp.status_code == 404

    def test_revoked_user_returns_404(self, sudo_client, db_session):
        user = User(
            username="revtest",
            admin_id=1,
            subscription_token="revoked-token",
            revoked=True,
            data_used=0,
        )
        db_session.add(user)
        db_session.commit()

        resp = sudo_client.get("/sub/revoked-token")
        assert resp.status_code == 404

    def test_invalid_token_returns_404(self, sudo_client):
        resp = sudo_client.get("/sub/nonexistent-token")
        assert resp.status_code == 404


# ===========================================================================
# 5. Password Leak Prevention
# ===========================================================================

class TestPasswordLeakPrevention:
    def test_admin_response_no_password(self, sudo_client, db_session):
        """Admin response must never contain password or hashed_password."""
        resp = sudo_client.get("/api/admins")
        assert resp.status_code == 200
        for admin in resp.json():
            assert "password" not in admin
            assert "hashed_password" not in admin
            assert "data" not in admin or "password" not in str(admin)

    def test_user_response_no_subscription_token(self, sudo_client, db_session):
        """User response must not expose subscription_token."""
        resp = sudo_client.get("/api/users")
        assert resp.status_code == 200
        for user in resp.json():
            assert "subscription_token" not in user

    def test_me_endpoint_no_password(self, sudo_client):
        resp = sudo_client.get("/api/admin/me")
        assert resp.status_code == 200
        data = resp.json()
        assert "password" not in data
        assert "hashed_password" not in data


# ===========================================================================
# 6. Job Thread Lock Guards
# ===========================================================================

class TestJobThreadLocks:
    def test_sync_usage_lock_skips_concurrent(self):
        """sync_usage_job should skip if previous run is still in progress."""
        from app.jobs.sync_usage import _job_lock, sync_usage_job

        acquired = [False]

        def hold_lock():
            _job_lock.acquire(blocking=True)
            acquired[0] = True
            time.sleep(0.5)
            _job_lock.release()

        # Hold the lock in a background thread
        t = threading.Thread(target=hold_lock)
        t.start()
        time.sleep(0.05)  # Let the thread acquire the lock

        # This should skip immediately
        with patch("app.jobs.sync_usage.get_live_status") as mock_status:
            sync_usage_job()
            mock_status.assert_not_called()

        t.join()

    def test_enforce_limits_lock_skips_concurrent(self):
        """enforce_limits_job should skip if previous run is still in progress."""
        from app.jobs.enforce_limits import _job_lock, enforce_limits_job

        _job_lock.acquire(blocking=True)

        with patch("app.db.SessionLocal") as mock_sl:
            enforce_limits_job()
            mock_sl.assert_not_called()

        _job_lock.release()

    def test_reset_periodic_lock_skips_concurrent(self):
        """reset_periodic_limits_job should skip if previous run is still in progress."""
        from app.jobs.reset_periodic_limits import _job_lock, reset_periodic_limits_job

        _job_lock.acquire(blocking=True)

        with patch("app.db.SessionLocal") as mock_sl:
            reset_periodic_limits_job()
            mock_sl.assert_not_called()

        _job_lock.release()


# ===========================================================================
# 7. Input Validation — positive integers and sane dates
# ===========================================================================

class TestInputValidation:
    def test_validate_positive_int_allows_none(self):
        validate_positive_int(None, "test")

    def test_validate_positive_int_allows_zero(self):
        validate_positive_int(0, "test")

    def test_validate_positive_int_allows_positive(self):
        validate_positive_int(100, "test")

    def test_validate_positive_int_rejects_negative(self):
        with pytest.raises(ValueError):
            validate_positive_int(-1, "test")

    def test_validate_sane_datetime_allows_none(self):
        validate_sane_datetime(None, "test")

    def test_validate_sane_datetime_allows_future(self):
        future = dt.datetime.now(dt.UTC) + dt.timedelta(days=30)
        validate_sane_datetime(future, "test")

    def test_validate_sane_datetime_rejects_old_past(self):
        past = dt.datetime.now(dt.UTC) - dt.timedelta(days=365)
        with pytest.raises(ValueError):
            validate_sane_datetime(past, "expire_at")

    def test_validate_time_window_valid(self):
        start = dt.time(8, 0)
        end = dt.time(22, 0)
        validate_time_window(start, end)

    def test_validate_time_window_rejects_start_after_end(self):
        start = dt.time(22, 0)
        end = dt.time(8, 0)
        with pytest.raises(ValueError):
            validate_time_window(start, end)

    def test_validate_time_window_allows_none(self):
        validate_time_window(None, None)
        validate_time_window(dt.time(8, 0), None)
        validate_time_window(None, dt.time(22, 0))


# ===========================================================================
# 8. CORS Configuration
# ===========================================================================

class TestCORSConfiguration:
    def test_cors_not_wildcard_in_prod(self):
        """CORS origins must not be wildcard in production."""
        from app.config import CORS_ORIGINS

        # In test environment, origins should be localhost
        # In production, they should be set to actual frontend URLs
        # The key assertion is that * is never in the list
        assert "*" not in CORS_ORIGINS

    def test_cors_credentials_true(self):
        from app.config import CORS_ALLOW_CREDENTIALS
        assert CORS_ALLOW_CREDENTIALS is True
