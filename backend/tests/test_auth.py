"""Tests for JWT auth — login, refresh, password-reset invalidation."""

from app.models.admin import Admin
from app.utils.password import hash_password


def _create_admin(db, username="admin", password="secret", is_sudo=True):
    """Helper to create an admin directly in the DB."""
    admin = Admin(
        username=username,
        hashed_password=hash_password(password),
        is_sudo=is_sudo,
        disabled=False,
        data_limit=None if is_sudo else 10 * 1024**3,
        data_used=0,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


class TestTokenEndpoint:
    def test_login_returns_tokens(self, client, db_session):
        _create_admin(db_session, "alice", "pass123")
        resp = client.post("/api/admin/token", json={"username": "alice", "password": "pass123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client, db_session):
        _create_admin(db_session, "bob", "correct")
        resp = client.post("/api/admin/token", json={"username": "bob", "password": "wrong"})
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/admin/token", json={"username": "ghost", "password": "x"})
        assert resp.status_code == 401

    def test_login_disabled_admin(self, client, db_session):
        admin = _create_admin(db_session, "disabled_user", "pass")
        admin.disabled = True
        db_session.commit()
        resp = client.post("/api/admin/token", json={"username": "disabled_user", "password": "pass"})
        assert resp.status_code == 403


class TestRefreshEndpoint:
    def test_refresh_returns_new_tokens(self, client, db_session):
        _create_admin(db_session, "charlie", "pass")
        login_resp = client.post("/api/admin/token", json={"username": "charlie", "password": "pass"})
        refresh_token = login_resp.json()["refresh_token"]

        resp = client.post("/api/admin/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_with_invalid_token(self, client):
        resp = client.post("/api/admin/refresh", json={"refresh_token": "garbage"})
        assert resp.status_code == 401

    def test_refresh_with_access_token_fails(self, client, db_session):
        _create_admin(db_session, "dave", "pass")
        login_resp = client.post("/api/admin/token", json={"username": "dave", "password": "pass"})
        access_token = login_resp.json()["access_token"]

        # Using an access token as refresh should fail
        resp = client.post("/api/admin/refresh", json={"refresh_token": access_token})
        assert resp.status_code == 401


class TestPasswordResetInvalidation:
    def test_old_token_rejected_after_password_reset(self, client, db_session):
        """After admin password is reset, old access tokens should be rejected."""
        admin = _create_admin(db_session, "eve", "oldpass")

        # Get a token with the old password
        login_resp = client.post("/api/admin/token", json={"username": "eve", "password": "oldpass"})
        old_access = login_resp.json()["access_token"]

        # Verify the old token works
        resp = client.get("/api/admin/me", headers={"Authorization": f"Bearer {old_access}"})
        assert resp.status_code == 200

        # Reset password (this sets password_reset_at)
        import datetime as dt
        admin.hashed_password = hash_password("newpass")
        admin.password_reset_at = dt.datetime.now(dt.UTC)
        db_session.commit()

        # Old token should now be rejected
        resp = client.get("/api/admin/me", headers={"Authorization": f"Bearer {old_access}"})
        assert resp.status_code == 401

        # New token with new password should work
        login_resp = client.post("/api/admin/token", json={"username": "eve", "password": "newpass"})
        assert login_resp.status_code == 200
        new_access = login_resp.json()["access_token"]
        resp = client.get("/api/admin/me", headers={"Authorization": f"Bearer {new_access}"})
        assert resp.status_code == 200


class TestGetMe:
    def test_me_returns_admin_profile(self, sudo_client):
        resp = sudo_client.get("/api/admin/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "admin"
        assert data["is_sudo"] is True
        assert data["data_limit"] is None

    def test_me_requires_auth(self, client):
        resp = client.get("/api/admin/me")
        assert resp.status_code == 401
