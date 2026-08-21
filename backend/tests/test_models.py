"""Tests for model constraints — uniqueness, cascade behavior, defaults."""

import secrets

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.admin import Admin
from app.models.admin_log import AdminAction, AdminLog, TargetType
from app.models.server_config import Cipher, DNSPreset, Protocol, ServerConfig, TLSSettings
from app.models.usage_log import UsageLog
from app.models.user import DataLimitResetStrategy, User, UserStatus


# ---------------------------------------------------------------------------
# Helper to create a hashed password (avoids importing passlib in model code)
# ---------------------------------------------------------------------------
def _hash(pw: str) -> str:
    from passlib.context import CryptContext

    return CryptContext(schemes=["bcrypt"], deprecated="auto").hash(pw)


# ===========================================================================
# Admin model
# ===========================================================================


class TestAdminModel:
    def test_create_admin(self, db_session):
        admin = Admin(
            username="alice",
            hashed_password=_hash("secret"),
            is_sudo=True,
            disabled=False,
            data_limit=None,
            data_used=0,
        )
        db_session.add(admin)
        db_session.commit()
        assert admin.id is not None
        assert admin.username == "alice"
        assert admin.is_sudo is True
        assert admin.data_limit is None
        assert admin.data_used == 0

    def test_username_uniqueness(self, db_session):
        a1 = Admin(username="bob", hashed_password=_hash("pw"), is_sudo=False)
        a2 = Admin(username="bob", hashed_password=_hash("pw2"), is_sudo=False)
        db_session.add(a1)
        db_session.commit()
        db_session.add(a2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_non_sudo_has_data_limit(self, db_session):
        admin = Admin(
            username="reseller",
            hashed_password=_hash("pw"),
            is_sudo=False,
            data_limit=10 * 1024**3,  # 10 GB
            data_used=0,
        )
        db_session.add(admin)
        db_session.commit()
        assert admin.data_limit == 10 * 1024**3

    def test_parent_admin_relationship(self, db_session):
        sudo = Admin(username="sudo", hashed_password=_hash("pw"), is_sudo=True)
        db_session.add(sudo)
        db_session.flush()

        child = Admin(
            username="child",
            hashed_password=_hash("pw"),
            is_sudo=False,
            parent_admin_id=sudo.id,
            data_limit=5 * 1024**3,
        )
        db_session.add(child)
        db_session.commit()

        assert child.parent_admin_id == sudo.id
        assert child in sudo.child_admins
        assert child.parent_admin == sudo


# ===========================================================================
# User model
# ===========================================================================


class TestUserModel:
    def _make_admin(self, db_session, username="owner"):
        admin = Admin(
            username=username, hashed_password=_hash("pw"), is_sudo=True, data_used=0
        )
        db_session.add(admin)
        db_session.flush()
        return admin

    def test_create_user(self, db_session):
        admin = self._make_admin(db_session)
        user = User(
            username="client-01",
            admin_id=admin.id,
            data_limit=1024**3,
            data_used=0,
        )
        db_session.add(user)
        db_session.commit()
        assert user.id is not None
        assert user.status == UserStatus.ACTIVE
        assert user.data_limit_reset_strategy == DataLimitResetStrategy.NO_RESET
        assert user.revoked is False
        assert len(user.subscription_token) > 20  # auto-generated

    def test_subscription_token_unique(self, db_session):
        admin = self._make_admin(db_session)
        token = secrets.token_urlsafe(32)
        u1 = User(username="a", admin_id=admin.id, subscription_token=token)
        u2 = User(username="b", admin_id=admin.id, subscription_token=token)
        db_session.add(u1)
        db_session.commit()
        db_session.add(u2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_username_uniqueness(self, db_session):
        admin = self._make_admin(db_session)
        u1 = User(username="same-name", admin_id=admin.id)
        u2 = User(username="same-name", admin_id=admin.id)
        db_session.add(u1)
        db_session.commit()
        db_session.add(u2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_subscription_token_auto_generated(self, db_session):
        admin = self._make_admin(db_session)
        user = User(username="auto-token", admin_id=admin.id)
        db_session.add(user)
        db_session.commit()
        assert user.subscription_token != ""
        assert len(user.subscription_token) >= 30

    def test_unique_subscription_token_generated(self, db_session):
        admin = self._make_admin(db_session)
        users = [User(username=f"u-{i}", admin_id=admin.id) for i in range(10)]
        db_session.add_all(users)
        db_session.commit()
        tokens = [u.subscription_token for u in users]
        assert len(set(tokens)) == 10  # all unique


# ===========================================================================
# Cascade: block admin deletion if users exist (RESTRICT)
# ===========================================================================


class TestAdminDeletionRestrict:
    def test_cannot_delete_admin_with_users(self, db_session):
        admin = Admin(
            username="has-users", hashed_password=_hash("pw"), is_sudo=True, data_used=0
        )
        db_session.add(admin)
        db_session.flush()

        user = User(username="orphan-me-not", admin_id=admin.id)
        db_session.add(user)
        db_session.commit()

        # Deleting the admin should fail because users reference it (RESTRICT).
        db_session.delete(admin)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_can_delete_admin_without_users(self, db_session):
        admin = Admin(
            username="no-users", hashed_password=_hash("pw"), is_sudo=True, data_used=0
        )
        db_session.add(admin)
        db_session.commit()

        db_session.delete(admin)
        db_session.commit()
        assert db_session.query(Admin).count() == 0


# ===========================================================================
# UsageLog model
# ===========================================================================


class TestUsageLogModel:
    def test_create_usage_log(self, db_session):
        admin = Admin(username="a", hashed_password=_hash("pw"), is_sudo=True, data_used=0)
        db_session.add(admin)
        db_session.flush()
        user = User(username="u", admin_id=admin.id)
        db_session.add(user)
        db_session.flush()

        log = UsageLog(user_id=user.id, bytes_sent=1024, bytes_received=2048)
        db_session.add(log)
        db_session.commit()
        assert log.id is not None
        assert log.bytes_sent == 1024
        assert log.bytes_received == 2048
        assert log.timestamp is not None

    def test_cascade_delete_user_deletes_logs(self, db_session):
        admin = Admin(username="a", hashed_password=_hash("pw"), is_sudo=True, data_used=0)
        db_session.add(admin)
        db_session.flush()
        user = User(username="u", admin_id=admin.id)
        db_session.add(user)
        db_session.flush()

        log = UsageLog(user_id=user.id, bytes_sent=100, bytes_received=200)
        db_session.add(log)
        db_session.commit()

        db_session.delete(user)
        db_session.commit()
        assert db_session.query(UsageLog).count() == 0


# ===========================================================================
# AdminLog model
# ===========================================================================


class TestAdminLogModel:
    def test_create_admin_log(self, db_session):
        admin = Admin(username="a", hashed_password=_hash("pw"), is_sudo=True, data_used=0)
        db_session.add(admin)
        db_session.flush()

        log = AdminLog(
            admin_id=admin.id,
            action=AdminAction.CREATE_USER,
            target_type=TargetType.USER,
            target_id=42,
            detail="Created user test-user",
        )
        db_session.add(log)
        db_session.commit()
        assert log.id is not None
        assert log.action == AdminAction.CREATE_USER
        assert log.timestamp is not None


# ===========================================================================
# ServerConfig model
# ===========================================================================


class TestServerConfigModel:
    def test_create_server_config(self, db_session):
        config = ServerConfig(
            protocol=Protocol.UDP,
            port=1194,
            interface="tun0",
            cipher=Cipher.AES_256_GCM,
            tls_mode=TLSSettings.TLS_CRYPT,
            dns_preset=DNSPreset.CLOUDFLARE,
            keepalive_interval=10,
            keepalive_timeout=120,
            client_to_client=False,
            redirect_gateway=True,
            public_host="vpn.example.com",
            subscription_url_prefix="https://panel.example.com",
        )
        db_session.add(config)
        db_session.commit()
        assert config.id is not None
        assert config.protocol == Protocol.UDP
        assert config.port == 1194
        assert config.cipher == Cipher.AES_256_GCM
        assert config.public_host == "vpn.example.com"

    def test_dns_servers_json(self, db_session):
        config = ServerConfig(
            protocol=Protocol.TCP,
            port=443,
            interface="tun0",
            cipher=Cipher.CHACHA20_POLY1305,
            tls_mode=TLSSettings.TLS_AUTH,
            dns_preset=DNSPreset.CUSTOM,
            dns_servers=["1.1.1.1", "1.0.0.1"],
            keepalive_interval=10,
            keepalive_timeout=120,
            client_to_client=True,
            redirect_gateway=False,
            public_host="",
            subscription_url_prefix="",
        )
        db_session.add(config)
        db_session.commit()
        assert config.dns_servers == ["1.1.1.1", "1.0.0.1"]


# ===========================================================================
# Seed function
# ===========================================================================


class TestSeed:
    def test_seed_creates_sudo_admin(self, db_session):
        from app.db.seed import seed_sudo_admin

        seed_sudo_admin(db_session)
        db_session.commit()

        admin = db_session.query(Admin).first()
        assert admin is not None
        assert admin.is_sudo is True
        assert admin.data_limit is None

    def test_seed_is_idempotent(self, db_session):
        from app.db.seed import seed_sudo_admin

        seed_sudo_admin(db_session)
        db_session.commit()
        seed_sudo_admin(db_session)
        db_session.commit()

        assert db_session.query(Admin).count() == 1

    def test_seed_creates_default_server_config(self, db_session):
        from app.db.seed import seed_default_server_config

        seed_default_server_config(db_session)
        db_session.commit()

        config = db_session.query(ServerConfig).first()
        assert config is not None
        assert config.protocol == Protocol.UDP
        assert config.port == 1194
        assert config.cipher == Cipher.AES_128_CBC
        assert config.dns_preset == DNSPreset.CLOUDFLARE

    def test_seed_server_config_idempotent(self, db_session):
        from app.db.seed import seed_default_server_config

        seed_default_server_config(db_session)
        db_session.commit()
        seed_default_server_config(db_session)
        db_session.commit()

        assert db_session.query(ServerConfig).count() == 1

    def test_seed_all(self, db_session):
        from app.db.seed import seed_all

        seed_all(db_session)
        db_session.commit()

        assert db_session.query(Admin).count() == 1
        assert db_session.query(ServerConfig).count() == 1
