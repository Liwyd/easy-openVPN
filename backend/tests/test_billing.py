"""Tests for the billing system — live-computed debt from CREATED volume."""

from __future__ import annotations

from app.models.admin import Admin
from app.models.billing import BillingRecord, BillingType
from app.models.user import User
from app.utils.password import hash_password


def _make_sub_admin(db, username="sub1", price_per_gb=None, price_per_user=None):
    sudo = db.query(Admin).filter(Admin.is_sudo.is_(True)).first()
    admin = Admin(
        username=username,
        hashed_password=hash_password("pass"),
        is_sudo=False,
        disabled=False,
        data_limit=None,
        data_used=0,
        parent_admin_id=sudo.id,
        price_per_gb=price_per_gb,
        price_per_user=price_per_user,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def _make_volumed_user(db, admin, username, data_limit_gb):
    user = User(
        username=username,
        admin_id=admin.id,
        data_limit=data_limit_gb * 1024 ** 3,
        data_used=0,
    )
    db.add(user)
    db.commit()
    return user


def _summary_for(db, username="sub1"):
    return db.query(Admin).filter(Admin.username == username).first()


class TestBillingDebt:
    def test_debt_from_created_volume_immediately(self, sudo_client, db_session):
        """Debt appears in /billing/summary right away, without the daily job.

        It must be based on the CREATED volume (sum of data_limit), not on
        consumed usage (data_used stays 0).
        """
        admin = _make_sub_admin(db_session, price_per_gb=10.0)
        _make_volumed_user(db_session, admin, "v1", data_limit_gb=100)
        _make_volumed_user(db_session, admin, "v2", data_limit_gb=50)

        resp = sudo_client.get("/api/billing/summary")
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 1
        row = rows[0]
        assert row["username"] == "sub1"
        # 150 GB created × $10 = $1500, regardless of data_used (0 bytes consumed)
        assert row["debt"] == 1500.0
        assert row["volumed_user_count"] == 2
        assert row["data_used"] == 0

    def test_no_pricing_means_no_debt(self, sudo_client, db_session):
        admin = _make_sub_admin(db_session)  # no pricing
        _make_volumed_user(db_session, admin, "v1", data_limit_gb=100)

        resp = sudo_client.get("/api/billing/summary")
        assert resp.status_code == 200
        assert resp.json()[0]["debt"] == 0.0

    def test_settlement_reduces_debt(self, sudo_client, db_session):
        admin = _make_sub_admin(db_session, price_per_gb=10.0)
        _make_volumed_user(db_session, admin, "v1", data_limit_gb=100)

        admin_id = admin.id
        resp = sudo_client.post(f"/api/billing/{admin_id}/settle", json={"amount": 400.0})
        assert resp.status_code == 200
        assert resp.json()["type"] == "settlement"
        assert resp.json()["amount"] == -400.0

        resp = sudo_client.get("/api/billing/summary")
        assert resp.json()[0]["debt"] == 1000.0 - 400.0

    def test_settlement_cannot_exceed_debt(self, sudo_client, db_session):
        admin = _make_sub_admin(db_session, price_per_gb=10.0)
        _make_volumed_user(db_session, admin, "v1", data_limit_gb=100)

        resp = sudo_client.post(
            f"/api/billing/{admin.id}/settle", json={"amount": 5000.0}
        )
        assert resp.status_code == 422

    def test_daily_job_keeps_settlements(self, sudo_client, db_session):
        """The daily job must NOT resurrect already-settled debt."""
        from app.jobs.billing import _process_admin

        admin = _make_sub_admin(db_session, price_per_gb=10.0)
        _make_volumed_user(db_session, admin, "v1", data_limit_gb=100)

        # settle $400 of the $1000 debt
        resp = sudo_client.post(f"/api/billing/{admin.id}/settle", json={"amount": 400.0})
        assert resp.status_code == 200

        _process_admin(admin, db_session)
        db_session.refresh(admin)
        assert admin.debt == 1000.0 - 400.0

        # records were still written as an audit trail
        records = db_session.query(BillingRecord).filter(
            BillingRecord.admin_id == admin.id,
            BillingRecord.type == BillingType.TRAFFIC_CHARGE,
        ).all()
        assert len(records) == 1

    def test_sub_admin_sees_own_debt(self, client, db_session):
        from app.db.seed import seed_sudo_admin
        seed_sudo_admin(db_session)
        db_session.commit()

        admin = _make_sub_admin(db_session, price_per_gb=5.0)
        _make_volumed_user(db_session, admin, "v1", data_limit_gb=200)

        resp = client.post("/api/admin/token", json={"username": "sub1", "password": "pass"})
        assert resp.status_code == 200
        token = resp.json()["access_token"]

        resp = client.get(
            "/api/billing/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        assert resp.json()["debt"] == 1000.0  # 200 GB × $5
