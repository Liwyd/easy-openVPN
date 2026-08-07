"""Tests for admin CRUD — sudo-only admin management with quota validation."""

from app.models.admin import Admin
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


class TestCreateAdmin:
    def test_sudo_creates_sub_admin(self, sudo_client, db_session):
        resp = sudo_client.post(
            "/api/admins",
            json={"username": "reseller1", "password": "pass", "data_limit": 10 * 1024**3},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "reseller1"
        assert data["is_sudo"] is False
        assert data["data_limit"] == 10 * 1024**3

    def test_non_sudo_cannot_create_admin(self, client, db_session):
        sudo = _create_admin(db_session, "sudo1", is_sudo=True)
        _create_admin(db_session, "sub1", data_limit=5 * 1024**3, parent_admin_id=sudo.id)
        db_session.commit()

        # Login as sub-admin
        resp = client.post("/api/admin/token", json={"username": "sub1", "password": "pass"})
        token = resp.json()["access_token"]

        resp = client.post(
            "/api/admins",
            json={"username": "newadmin", "password": "pass", "data_limit": 1 * 1024**3},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_quota_guard_rejects_over_allocation(self, sudo_client, db_session):
        # Create a sub-admin with 5 GB limit
        sudo_client.post(
            "/api/admins",
            json={"username": "limited", "password": "pass", "data_limit": 5 * 1024**3},
        )

        # The sudo admin has no limit, so creating admins succeeds.
        # To test the quota guard, login as "limited" (5GB) and try to
        # create a user with 10GB limit — that should fail.
        login_resp = sudo_client.post("/api/admin/token", json={"username": "limited", "password": "pass"})
        sub_token = login_resp.json()["access_token"]

        resp = sudo_client.post(
            "/api/users",
            json={"username": "biguser", "data_limit": 10 * 1024**3},
            headers={"Authorization": f"Bearer {sub_token}"},
        )
        assert resp.status_code == 409

    def test_duplicate_username_rejected(self, sudo_client, db_session):
        sudo_client.post(
            "/api/admins",
            json={"username": "dup", "password": "pass", "data_limit": 1 * 1024**3},
        )
        resp = sudo_client.post(
            "/api/admins",
            json={"username": "dup", "password": "pass2", "data_limit": 2 * 1024**3},
        )
        assert resp.status_code == 409


class TestListAdmins:
    def test_sudo_lists_admins(self, sudo_client, db_session):
        _create_admin(db_session, "child1", data_limit=1 * 1024**3, parent_admin_id=1)
        _create_admin(db_session, "child2", data_limit=2 * 1024**3, parent_admin_id=1)
        db_session.commit()

        resp = sudo_client.get("/api/admins")
        assert resp.status_code == 200
        # Should return at least the 2 children (the sudo admin itself
        # is not listed because parent_admin_id filter excludes it).
        usernames = [a["username"] for a in resp.json()]
        assert "child1" in usernames
        assert "child2" in usernames


class TestGetAdmin:
    def test_sudo_gets_admin(self, sudo_client, db_session):
        admin = _create_admin(db_session, "target", data_limit=5 * 1024**3, parent_admin_id=1)
        db_session.commit()
        resp = sudo_client.get(f"/api/admins/{admin.id}")
        assert resp.status_code == 200
        assert resp.json()["username"] == "target"

    def test_get_nonexistent_admin(self, sudo_client):
        resp = sudo_client.get("/api/admins/99999")
        assert resp.status_code == 404


class TestUpdateAdmin:
    def test_change_data_limit(self, sudo_client, db_session):
        admin = _create_admin(db_session, "editable", data_limit=5 * 1024**3, parent_admin_id=1)
        db_session.commit()
        resp = sudo_client.put(
            f"/api/admins/{admin.id}",
            json={"data_limit": 10 * 1024**3},
        )
        assert resp.status_code == 200
        assert resp.json()["data_limit"] == 10 * 1024**3

    def test_reduce_limit_below_allocation_rejected(self, sudo_client, db_session):
        admin = _create_admin(db_session, "parent", data_limit=10 * 1024**3, parent_admin_id=1)
        db_session.commit()
        # Create a user under this admin with 5 GB limit
        from app.models.user import User

        user = User(username="u1", admin_id=admin.id, data_limit=5 * 1024**3, data_used=0)
        db_session.add(user)
        db_session.commit()

        # Try to reduce admin limit to 3 GB (below 5 GB allocation)
        resp = sudo_client.put(
            f"/api/admins/{admin.id}",
            json={"data_limit": 3 * 1024**3},
        )
        assert resp.status_code == 409

    def test_disable_admin(self, sudo_client, db_session):
        admin = _create_admin(db_session, "disable_me", data_limit=1 * 1024**3, parent_admin_id=1)
        db_session.commit()
        resp = sudo_client.put(
            f"/api/admins/{admin.id}",
            json={"disabled": True},
        )
        assert resp.status_code == 200
        assert resp.json()["disabled"] is True

    def test_reset_password_invalidates_old_tokens(self, sudo_client, client, db_session):
        admin = _create_admin(db_session, "pwreset", password="old", data_limit=1 * 1024**3, parent_admin_id=1)
        db_session.commit()

        # Login with old password
        login_resp = client.post("/api/admin/token", json={"username": "pwreset", "password": "old"})
        old_token = login_resp.json()["access_token"]

        # Verify old token works
        resp = client.get("/api/admin/me", headers={"Authorization": f"Bearer {old_token}"})
        assert resp.status_code == 200

        # Sudo resets the password
        resp = sudo_client.put(
            f"/api/admins/{admin.id}",
            json={"password": "new"},
        )
        assert resp.status_code == 200

        # Old token should be rejected
        resp = client.get("/api/admin/me", headers={"Authorization": f"Bearer {old_token}"})
        assert resp.status_code == 401


class TestDeleteAdmin:
    def test_delete_admin_without_users(self, sudo_client, db_session):
        admin = _create_admin(db_session, "delete_me", data_limit=1 * 1024**3, parent_admin_id=1)
        db_session.commit()
        resp = sudo_client.delete(f"/api/admins/{admin.id}")
        assert resp.status_code == 204

    def test_delete_admin_with_users_blocked(self, sudo_client, db_session):
        admin = _create_admin(db_session, "has_users", data_limit=5 * 1024**3, parent_admin_id=1)
        db_session.commit()
        from app.models.user import User

        user = User(username="u1", admin_id=admin.id, data_used=0)
        db_session.add(user)
        db_session.commit()

        resp = sudo_client.delete(f"/api/admins/{admin.id}")
        assert resp.status_code == 409
        assert "user(s) still assigned" in resp.json()["detail"]

    def test_delete_admin_with_children_blocked(self, sudo_client, db_session):
        admin = _create_admin(db_session, "has_children", data_limit=10 * 1024**3, parent_admin_id=1)
        db_session.commit()
        _create_admin(db_session, "child_a", data_limit=1 * 1024**3, parent_admin_id=admin.id)
        db_session.commit()

        resp = sudo_client.delete(f"/api/admins/{admin.id}")
        assert resp.status_code == 409
        assert "sub-admin(s) still report" in resp.json()["detail"]

    def test_cannot_delete_sudo_admin(self, sudo_client, db_session):
        sudo = db_session.query(Admin).filter(Admin.is_sudo.is_(True)).first()
        resp = sudo_client.delete(f"/api/admins/{sudo.id}")
        assert resp.status_code == 403


class TestAdminUsage:
    def test_usage_breakdown(self, sudo_client, db_session):
        admin = _create_admin(db_session, "usage_admin", data_limit=10 * 1024**3, parent_admin_id=1)
        db_session.commit()
        from app.models.user import User

        u1 = User(username="u1", admin_id=admin.id, data_limit=3 * 1024**3, data_used=1 * 1024**3)
        u2 = User(username="u2", admin_id=admin.id, data_limit=5 * 1024**3, data_used=2 * 1024**3)
        db_session.add_all([u1, u2])
        db_session.commit()

        resp = sudo_client.get(f"/api/admins/{admin.id}/usage")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data_limit"] == 10 * 1024**3
        assert data["direct_users_bytes"] == 3 * 1024**3
