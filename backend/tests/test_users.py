"""Tests for user CRUD — quota-aware user management."""

from unittest.mock import patch

from app.db.seed import seed_sudo_admin
from app.models.admin import Admin
from app.models.user import User
from app.utils.password import hash_password


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
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _get_sudo(db):
    """Get or create the sudo admin, return it."""
    existing = db.query(Admin).filter(Admin.is_sudo.is_(True)).first()
    if existing:
        return existing
    seed_sudo_admin(db)
    db.commit()
    return db.query(Admin).filter(Admin.is_sudo.is_(True)).first()


class TestCreateUser:
    @patch("app.routers.users._create_client_cert")
    def test_sudo_creates_user(self, mock_cert, sudo_client):
        mock_cert.return_value = "ovpn-content"
        resp = sudo_client.post(
            "/api/users",
            json={"username": "vpn-user-1", "data_limit": 1024**3},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "vpn-user-1"
        assert data["data_limit"] == 1024**3
        assert len(data["subscription_token"]) > 20

    @patch("app.routers.users._create_client_cert")
    def test_sub_admin_creates_user_within_quota(self, mock_cert, client, db_session):
        mock_cert.return_value = "ovpn-content"
        sudo = _get_sudo(db_session)
        _create_admin(db_session, "sub_a", data_limit=5 * 1024**3, parent_admin_id=sudo.id)
        headers = _login(client, "sub_a")

        resp = client.post(
            "/api/users",
            json={"username": "u1", "data_limit": 2 * 1024**3},
            headers=headers,
        )
        assert resp.status_code == 201

    def test_quota_guard_rejects_over_limit(self, client, db_session):
        sudo = _get_sudo(db_session)
        _create_admin(db_session, "sub_b", data_limit=3 * 1024**3, parent_admin_id=sudo.id)
        headers = _login(client, "sub_b")

        resp = client.post(
            "/api/users",
            json={"username": "big_u", "data_limit": 10 * 1024**3},
            headers=headers,
        )
        assert resp.status_code == 409
        assert "quota" in resp.json()["detail"].lower()

    @patch("app.routers.users._create_client_cert")
    def test_duplicate_username_rejected(self, mock_cert, sudo_client):
        mock_cert.return_value = "ovpn-content"
        sudo_client.post("/api/users", json={"username": "dup_u", "data_limit": 1024**3})
        resp = sudo_client.post("/api/users", json={"username": "dup_u", "data_limit": 2048})
        assert resp.status_code == 409

    @patch("app.routers.users._create_client_cert")
    def test_unlimited_user_on_sudo(self, mock_cert, sudo_client):
        mock_cert.return_value = "ovpn-content"
        resp = sudo_client.post("/api/users", json={"username": "unlimited_u"})
        assert resp.status_code == 201
        assert resp.json()["data_limit"] is None


class TestListUsers:
    @patch("app.routers.users._create_client_cert")
    def test_sudo_sees_all_users(self, mock_cert, sudo_client):
        mock_cert.return_value = "ovpn-content"
        sudo_client.post("/api/users", json={"username": "list_a", "data_limit": 1024})
        sudo_client.post("/api/users", json={"username": "list_b", "data_limit": 2048})
        resp = sudo_client.get("/api/users")
        assert resp.status_code == 200
        usernames = [u["username"] for u in resp.json()]
        assert "list_a" in usernames
        assert "list_b" in usernames

    @patch("app.routers.users._create_client_cert")
    def test_sub_admin_sees_only_own_users(self, mock_cert, client, db_session):
        mock_cert.return_value = "ovpn-content"
        sudo = _get_sudo(db_session)
        _create_admin(db_session, "sub_c", data_limit=10 * 1024**3, parent_admin_id=sudo.id)
        headers = _login(client, "sub_c")

        # Create a user via sub-admin
        client.post("/api/users", json={"username": "my_user", "data_limit": 1024}, headers=headers)

        # Create a user via sudo (using sudo's token directly)
        sudo_token_resp = client.post("/api/admin/token", json={"username": sudo.username, "password": "admin"})
        sudo_headers = {"Authorization": f"Bearer {sudo_token_resp.json()['access_token']}"}
        client.post("/api/users", json={"username": "sudo_user", "data_limit": 1024}, headers=sudo_headers)

        resp = client.get("/api/users", headers=headers)
        assert resp.status_code == 200
        usernames = [u["username"] for u in resp.json()]
        assert "my_user" in usernames
        assert "sudo_user" not in usernames


class TestGetUser:
    @patch("app.routers.users._create_client_cert")
    def test_get_own_user(self, mock_cert, client, db_session):
        mock_cert.return_value = "ovpn-content"
        sudo = _get_sudo(db_session)
        _create_admin(db_session, "sub_d", data_limit=10 * 1024**3, parent_admin_id=sudo.id)
        headers = _login(client, "sub_d")

        client.post("/api/users", json={"username": "fetch_me", "data_limit": 1024}, headers=headers)
        resp = client.get("/api/users/fetch_me", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["username"] == "fetch_me"

    def test_cannot_get_other_admin_user(self, client, db_session):
        sudo = _get_sudo(db_session)
        admin1 = _create_admin(db_session, "owner1", data_limit=10 * 1024**3, parent_admin_id=sudo.id)
        _create_admin(db_session, "owner2", data_limit=10 * 1024**3, parent_admin_id=sudo.id)

        # Create user under owner1 via sudo
        user = User(username="secret_user", admin_id=admin1.id, data_used=0)
        db_session.add(user)
        db_session.commit()

        # owner2 tries to access owner1's user — should get 404
        headers2 = _login(client, "owner2")
        resp = client.get("/api/users/secret_user", headers=headers2)
        assert resp.status_code == 404


class TestUpdateUser:
    @patch("app.routers.users._create_client_cert")
    def test_update_user_data_limit(self, mock_cert, client, db_session):
        mock_cert.return_value = "ovpn-content"
        sudo = _get_sudo(db_session)
        _create_admin(db_session, "sub_e", data_limit=10 * 1024**3, parent_admin_id=sudo.id)
        headers = _login(client, "sub_e")

        client.post("/api/users", json={"username": "upd_u", "data_limit": 1024}, headers=headers)
        resp = client.put("/api/users/upd_u", json={"data_limit": 2048}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["data_limit"] == 2048

    def test_increase_limit_beyond_quota_rejected(self, client, db_session):
        sudo = _get_sudo(db_session)
        _create_admin(db_session, "sub_f", data_limit=3 * 1024**3, parent_admin_id=sudo.id)
        headers = _login(client, "sub_f")

        # Create user directly in DB
        admin = db_session.query(Admin).filter(Admin.username == "sub_f").first()
        user = User(username="tight_u", admin_id=admin.id, data_limit=2 * 1024**3, data_used=0)
        db_session.add(user)
        db_session.commit()

        resp = client.put(
            "/api/users/tight_u",
            json={"data_limit": 5 * 1024**3},
            headers=headers,
        )
        assert resp.status_code == 409


class TestDeleteUser:
    def test_delete_user_recalcs_data_used(self, client, db_session):
        sudo = _get_sudo(db_session)
        _create_admin(db_session, "sub_g", data_limit=10 * 1024**3, parent_admin_id=sudo.id)
        headers = _login(client, "sub_g")

        # Create user directly in DB (bypassing vpn-core cert creation)
        admin = db_session.query(Admin).filter(Admin.username == "sub_g").first()
        user = User(username="del_u", admin_id=admin.id, data_limit=1024, data_used=0)
        db_session.add(user)
        db_session.commit()

        resp = client.delete("/api/users/del_u", headers=headers)
        assert resp.status_code == 204

        # Verify user is not in list (soft-deleted)
        resp = client.get("/api/users", headers=headers)
        usernames = [u["username"] for u in resp.json()]
        assert "del_u" not in usernames

    def test_cannot_delete_other_admin_user(self, client, db_session):
        sudo = _get_sudo(db_session)
        admin1 = _create_admin(db_session, "prot1", data_limit=10 * 1024**3, parent_admin_id=sudo.id)
        _create_admin(db_session, "prot2", data_limit=10 * 1024**3, parent_admin_id=sudo.id)

        # Create user under admin1
        user = User(username="protected_u", admin_id=admin1.id, data_used=0)
        db_session.add(user)
        db_session.commit()

        # admin2 tries to delete — should get 404
        headers2 = _login(client, "prot2")
        resp = client.delete("/api/users/protected_u", headers=headers2)
        assert resp.status_code == 404
