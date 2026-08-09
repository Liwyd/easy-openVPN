"""Tests that the bot module is resilient — never breaks the app.

Specifically: when TELEGRAM_ENABLED is False or the token/chat IDs are
missing, emit() must be a silent no-op and the rest of the application
must function normally.
"""

from __future__ import annotations

from unittest.mock import patch

from app.bot.config import is_configured
from app.bot.events import EventCategory, emit


class TestBotDisabled:
    """When the bot is not configured, emit must never raise."""

    @patch("app.bot.events.is_configured", return_value=False)
    def test_emit_user_created_is_noop(self, _mock_config):
        # Must not raise, must not attempt to send
        emit(
            category=EventCategory.ADMIN_ACTION,
            action="user_created",
            username="alice",
            admin_username="root",
        )

    @patch("app.bot.events.is_configured", return_value=False)
    def test_emit_sync_event_is_noop(self, _mock_config):
        emit(
            category=EventCategory.SYNC,
            action="usage_sync_tick",
        )

    def test_is_configured_false_when_no_token(self):
        with patch("app.bot.config.TELEGRAM_ENABLED", True), \
             patch("app.bot.config.TELEGRAM_BOT_TOKEN", ""), \
             patch("app.bot.config.TELEGRAM_ADMIN_CHAT_IDS", ["123"]):
            assert is_configured() is False

    def test_is_configured_false_when_no_chat_ids(self):
        with patch("app.bot.config.TELEGRAM_ENABLED", True), \
             patch("app.bot.config.TELEGRAM_BOT_TOKEN", "token123"), \
             patch("app.bot.config.TELEGRAM_ADMIN_CHAT_IDS", []):
            assert is_configured() is False

    def test_is_configured_false_when_disabled(self):
        with patch("app.bot.config.TELEGRAM_ENABLED", False), \
             patch("app.bot.config.TELEGRAM_BOT_TOKEN", "token123"), \
             patch("app.bot.config.TELEGRAM_ADMIN_CHAT_IDS", ["123"]):
            assert is_configured() is False

    def test_is_configured_true_when_all_set(self):
        with patch("app.bot.config.TELEGRAM_ENABLED", True), \
             patch("app.bot.config.TELEGRAM_BOT_TOKEN", "token123"), \
             patch("app.bot.config.TELEGRAM_ADMIN_CHAT_IDS", ["123"]):
            assert is_configured() is True


class TestBotDoesNotBreakEnforcement:
    """Verify that user creation/update/delete work even when bot send fails."""

    def test_user_create_works_with_telegram_failure(self, sudo_client):
        """User CRUD must succeed even if Telegram send raises."""
        with patch("app.bot.events.send_message", side_effect=Exception("Telegram down")), \
             patch("app.bot.events.is_configured", return_value=True), \
             patch("app.routers.users._create_client_cert", return_value=("serial", "cn")):
            resp = sudo_client.post(
                "/api/users",
                json={"username": "telegram_test_user", "data_limit": 1024},
            )
            assert resp.status_code == 201
            assert resp.json()["username"] == "telegram_test_user"

    def test_user_delete_works_with_telegram_failure(self, sudo_client):
        with patch("app.routers.users._create_client_cert", return_value=("serial", "cn")), \
             patch("app.routers.users._revoke_client_cert"), \
             patch("app.routers.users._kill_client_session"):
            resp = sudo_client.post(
                "/api/users",
                json={"username": "del_telegram_user", "data_limit": 1024},
            )
            assert resp.status_code == 201

        with patch("app.bot.events.send_message", side_effect=Exception("Telegram down")), \
             patch("app.bot.events.is_configured", return_value=True), \
             patch("app.routers.users._revoke_client_cert"), \
             patch("app.routers.users._kill_client_session"):
            resp = sudo_client.delete("/api/users/del_telegram_user")
            assert resp.status_code == 204

    def test_admin_create_works_with_telegram_failure(self, sudo_client):
        with patch("app.bot.events.send_message", side_effect=Exception("Telegram down")), \
             patch("app.bot.events.is_configured", return_value=True):
            resp = sudo_client.post(
                "/api/admins",
                json={
                    "username": "sub_telegram_admin",
                    "password": "pass",
                    "data_limit": 1024,
                    "is_sudo": False,
                },
            )
            assert resp.status_code == 201

    def test_user_update_works_with_telegram_failure(self, sudo_client):
        with patch("app.routers.users._create_client_cert", return_value=("serial", "cn")):
            resp = sudo_client.post(
                "/api/users",
                json={"username": "upd_telegram_user", "data_limit": 1024},
            )
            assert resp.status_code == 201

        with patch("app.bot.events.send_message", side_effect=Exception("Telegram down")), \
             patch("app.bot.events.is_configured", return_value=True):
            resp = sudo_client.put(
                "/api/users/upd_telegram_user",
                json={"data_limit": 2048},
            )
            assert resp.status_code == 200

    def test_sync_events_suppressed(self):
        """SYNC category events must never reach send_message."""
        with patch("app.bot.events.send_message") as mock_send, \
             patch("app.bot.events.is_configured", return_value=True):
            emit(
                category=EventCategory.SYNC,
                action="usage_sync_tick",
            )
            mock_send.assert_not_called()

    def test_enforcement_events_sent(self):
        """ENFORCEMENT events must reach send_message."""
        with patch("app.bot.events.send_message") as mock_send, \
             patch("app.bot.events.is_configured", return_value=True):
            emit(
                category=EventCategory.ENFORCEMENT,
                action="user_disabled_limit",
                username="bob",
            )
            mock_send.assert_called_once()


class TestTelegramTestEndpoint:
    def test_endpoint_requires_sudo(self, client, db_session):
        """Non-sudo admins should get 403."""
        from app.db.seed import seed_sudo_admin
        from app.models.admin import Admin
        from app.utils.password import hash_password

        seed_sudo_admin(db_session)
        db_session.commit()
        sudo = db_session.query(Admin).filter(Admin.is_sudo.is_(True)).first()

        non_sudo = Admin(
            username="regular_admin",
            hashed_password=hash_password("pass"),
            is_sudo=False,
            disabled=False,
            data_limit=1024,
            data_used=0,
            parent_admin_id=sudo.id,
        )
        db_session.add(non_sudo)
        db_session.commit()

        # Login as non-sudo
        resp = client.post("/api/admin/token", json={"username": "regular_admin", "password": "pass"})
        assert resp.status_code == 200
        token = resp.json()["access_token"]

        resp = client.post(
            "/api/settings/telegram/test",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_endpoint_returns_503_when_not_configured(self, sudo_client):
        """When Telegram is not configured, endpoint returns 503."""
        resp = sudo_client.post("/api/settings/telegram/test")
        assert resp.status_code == 503
        assert "not configured" in resp.json()["detail"].lower()
