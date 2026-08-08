"""Tests for bot message formatting — pure functions, no network."""

from app.bot.formatter import (
    EMOJI_CREATE,
    EMOJI_DELETE,
    EMOJI_DISABLE,
    EMOJI_ENABLE,
    EMOJI_ERROR,
    EMOJI_SYSTEM,
    _esc,
    _fmt_bytes,
    format_event,
)


class TestEscape:
    def test_escapes_special_chars(self):
        assert _esc("hello world") == "hello world"
        assert _esc("foo_bar") == "foo\\_bar"
        assert _esc("a(b)") == "a\\(b\\)"
        assert _esc("100%") == "100%"
        assert _esc("x*y") == "x\\*y"

    def test_none_returns_empty(self):
        assert _esc(None) == ""


class TestFmtBytes:
    def test_none_is_unlimited(self):
        assert _fmt_bytes(None) == "unlimited"

    def test_bytes(self):
        assert _fmt_bytes(0) == "0.0 B"
        assert _fmt_bytes(500) == "500.0 B"

    def test_kilobytes(self):
        assert _fmt_bytes(1024) == "1.0 KB"

    def test_megabytes(self):
        assert _fmt_bytes(1024**2) == "1.0 MB"

    def test_gigabytes(self):
        assert _fmt_bytes(10 * 1024**3) == "10.0 GB"

    def test_terabytes(self):
        assert _fmt_bytes(1024**4) == "1.0 TB"


class TestFormatEvent:
    def test_user_created(self):
        msg = format_event(
            action="user_created",
            username="alice",
            admin_username="root",
            data_limit=10 * 1024**3,
            expires="2026-09-01",
        )
        assert msg is not None
        assert EMOJI_CREATE in msg
        assert "alice" in msg
        assert "root" in msg
        assert "10.0 GB" in msg
        assert "expires" in msg

    def test_user_disabled_limit(self):
        msg = format_event(
            action="user_disabled_limit",
            username="bob",
            data_limit=10 * 1024**3,
            data_used=11 * 1024**3,
        )
        assert msg is not None
        assert EMOJI_DISABLE in msg
        assert "bob" in msg
        assert "11.0 GB" in msg

    def test_user_disabled_expired(self):
        msg = format_event(action="user_disabled_expired", username="carol")
        assert msg is not None
        assert EMOJI_DISABLE in msg
        assert "carol" in msg

    def test_admin_created(self):
        msg = format_event(
            action="admin_created",
            username="newadmin",
            admin_username="root",
            data_limit=50 * 1024**3,
        )
        assert msg is not None
        assert EMOJI_CREATE in msg
        assert "newadmin" in msg
        assert "50.0 GB" in msg

    def test_admin_deleted(self):
        msg = format_event(
            action="admin_deleted",
            username="oldadmin",
            admin_username="root",
        )
        assert msg is not None
        assert EMOJI_DELETE in msg
        assert "oldadmin" in msg

    def test_user_deleted(self):
        msg = format_event(
            action="user_deleted",
            username="deluser",
            admin_username="owner1",
        )
        assert msg is not None
        assert EMOJI_DELETE in msg
        assert "deluser" in msg

    def test_unknown_action_uses_error_emoji(self):
        msg = format_event(action="some_unknown_action")
        assert msg is not None
        assert EMOJI_ERROR in msg

    def test_minimal_event(self):
        msg = format_event(action="user_enabled", username="test")
        assert msg is not None
        assert EMOJI_ENABLE in msg
        assert "test" in msg

    def test_extra_field(self):
        msg = format_event(action="server_config_updated", extra="protocol changed to TCP")
        assert msg is not None
        assert EMOJI_SYSTEM in msg
        assert "protocol changed to TCP" in msg

    def test_unlimited_user(self):
        msg = format_event(action="user_created", username="nolimit", data_limit=None)
        assert msg is not None
        assert "unlimited" in msg

    def test_usage_percentage_displayed(self):
        msg = format_event(
            action="user_disabled_limit",
            username="u1",
            data_limit=10 * 1024**3,
            data_used=5 * 1024**3,
        )
        assert msg is not None
        assert "50%" in msg
