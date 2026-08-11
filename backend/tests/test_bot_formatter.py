"""Tests for bot message formatting — pure functions, no network."""

import datetime as dt

from app.bot.formatter import (
    EMOJI_CREATE,
    EMOJI_DELETE,
    EMOJI_DISABLE,
    EMOJI_ENABLE,
    EMOJI_ERROR,
    EMOJI_EXPIRED,
    EMOJI_LIMITED,
    EMOJI_MODIFY,
    EMOJI_SYSTEM,
    SEP,
    _fmt_bytes,
    format_backup_info,
    format_event,
)


class TestFmtBytes:
    def test_none_is_unlimited(self):
        assert _fmt_bytes(None) == "Unlimited"

    def test_bytes(self):
        assert _fmt_bytes(0) == "0.0 B"

    def test_kilobytes(self):
        assert _fmt_bytes(1024) == "1.0 KB"

    def test_megabytes(self):
        assert _fmt_bytes(1024**2) == "1.0 MB"

    def test_gigabytes(self):
        assert _fmt_bytes(10 * 1024**3) == "10.0 GB"


class TestFormatEvent:
    def test_user_created(self):
        msg = format_event(
            action="user_created",
            username="alice",
            admin_username="root",
            belongs_to="root",
            data_limit=10 * 1024**3,
            expires="2026-09-01",
        )
        assert msg is not None
        assert f"{EMOJI_CREATE} #Created" in msg
        assert "Username : alice" in msg
        assert "Traffic Limit : 10.0 GB" in msg
        assert "Expire Date : 2026-09-01" in msg
        assert "Belongs To : root" in msg
        assert "By : #root" in msg

    def test_expire_never_when_missing(self):
        msg = format_event(action="user_created", username="bob")
        assert msg is not None
        assert "Expire Date : Never" in msg

    def test_user_limited(self):
        msg = format_event(
            action="user_limited",
            username="bob",
            data_limit=10 * 1024**3,
            data_used=11 * 1024**3,
        )
        assert msg is not None
        assert f"{EMOJI_LIMITED} #Limited" in msg
        assert "bob" in msg
        assert "Usage : 11.0 GB/10.0 GB (110%)" in msg

    def test_user_expired(self):
        msg = format_event(action="user_expired", username="carol")
        assert msg is not None
        assert f"{EMOJI_EXPIRED} #Expired" in msg

    def test_user_disabled(self):
        msg = format_event(
            action="user_disabled_admin",
            username="dan",
            admin_username="root",
            belongs_to="owner",
        )
        assert msg is not None
        assert f"{EMOJI_DISABLE} #Disabled" in msg
        assert "Belongs To : owner" in msg

    def test_user_modified(self):
        msg = format_event(action="user_updated", username="eva", admin_username="root")
        assert msg is not None
        assert f"{EMOJI_MODIFY} #Modified" in msg
        assert "By : #root" in msg

    def test_user_deleted(self):
        msg = format_event(
            action="user_deleted",
            username="deluser",
            admin_username="owner1",
            belongs_to="owner1",
        )
        assert msg is not None
        assert f"{EMOJI_DELETE} #Deleted" in msg
        assert "deluser" in msg

    def test_admin_created(self):
        msg = format_event(
            action="admin_created",
            username="newadmin",
            admin_username="root",
            data_limit=50 * 1024**3,
        )
        assert msg is not None
        assert f"{EMOJI_CREATE} #Created" in msg
        assert "newadmin" in msg
        assert "50.0 GB" in msg

    def test_unknown_action_uses_error_emoji(self):
        msg = format_event(action="some_unknown_action")
        assert msg is not None
        assert EMOJI_ERROR in msg

    def test_minimal_event(self):
        msg = format_event(action="user_enabled", username="test")
        assert msg is not None
        assert f"{EMOJI_ENABLE} #Activated" in msg
        assert "test" in msg

    def test_extra_field(self):
        msg = format_event(action="server_config_updated", extra="protocol changed to TCP")
        assert msg is not None
        assert EMOJI_SYSTEM in msg
        assert "protocol changed to TCP" in msg

    def test_unlimited_user(self):
        msg = format_event(action="user_created", username="nolimit", data_limit=None)
        assert msg is not None
        assert "Traffic Limit : Unlimited" in msg

    def test_usage_percentage_displayed(self):
        msg = format_event(
            action="user_disabled_limit",
            username="u1",
            data_limit=10 * 1024**3,
            data_used=5 * 1024**3,
        )
        assert msg is not None
        assert "(50%)" in msg

    def test_separator_present(self):
        msg = format_event(action="user_created", username="x", admin_username="root")
        assert msg is not None
        assert SEP in msg


class TestBackupInfo:
    def test_format_backup_info(self):
        created_at = dt.datetime(2026, 8, 8, 22, 0, 3, tzinfo=dt.UTC)
        msg = format_backup_info("45.155.71.252", "backup_part_aa.tar.gz", created_at)
        assert "📦 Backup Information" in msg
        assert "🌐 Server IP: 45.155.71.252" in msg
        assert "📁 Backup File: backup_part_aa.tar.gz" in msg
        assert "⏰ Backup Time: 2026-08-08 22:00:03 UTC" in msg
