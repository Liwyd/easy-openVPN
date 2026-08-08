"""Message formatting — pure functions, easy to test without network.

Every ``format_*`` function returns a Markdown‑formatted string ready for
the Telegram Bot API (parse_mode=MarkdownV2).  All user / admin names
are escaped to avoid MarkdownV2 parse errors.

Emoji convention (defined once):
    create = 🟢
    disable / limit / expire = 🔴
    enable = 🟡
    admin action = 🛠️
    delete = ⚫
    error / warning = ⚠️
    system = 🔵
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ── Emoji constants ──────────────────────────────────────────────────
EMOJI_CREATE = "\U0001f7e2"  # 🟢
EMOJI_DISABLE = "\U0001f534"  # 🔴
EMOJI_ENABLE = "\U0001f7e1"  # 🟡
EMOJI_ADMIN = "\U0001f6e0\ufe0f"  # 🛠️
EMOJI_DELETE = "\u26ab"  # ⚫
EMOJI_ERROR = "\u26a0\ufe0f"  # ⚠️
EMOJI_SYSTEM = "\U0001f535"  # 🔵


def _esc(text: str | None) -> str:
    """Escape MarkdownV2 special characters."""
    if text is None:
        return ""
    # Characters that must be escaped in MarkdownV2
    specials = r"\_*[]()~`>#+-=|{}.!"
    out: list[str] = []
    for ch in str(text):
        if ch in specials:
            out.append("\\")
        out.append(ch)
    return "".join(out)


def _fmt_bytes(n: int | None) -> str:
    """Human-readable byte size."""
    if n is None:
        return "unlimited"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}"
        n /= 1024.0  # type: ignore[assignment]
    return f"{n:.1f} PB"


# ── Action → (emoji, verb) mapping ──────────────────────────────────
_ACTION_MAP: dict[str, tuple[str, str]] = {
    # User enforcement
    "user_created": (EMOJI_CREATE, "New user"),
    "user_disabled_limit": (EMOJI_DISABLE, "User disabled"),
    "user_disabled_expired": (EMOJI_DISABLE, "User disabled"),
    "user_disabled_admin": (EMOJI_DISABLE, "User disabled"),
    "user_enabled": (EMOJI_ENABLE, "User enabled"),
    "user_deleted": (EMOJI_DELETE, "User deleted"),
    "user_updated": (EMOJI_ADMIN, "User updated"),
    # Admin
    "admin_created": (EMOJI_CREATE, "New admin"),
    "admin_deleted": (EMOJI_DELETE, "Admin deleted"),
    "admin_disabled": (EMOJI_DISABLE, "Admin disabled"),
    "admin_enabled": (EMOJI_ENABLE, "Admin enabled"),
    "admin_updated": (EMOJI_ADMIN, "Admin updated"),
    # System
    "server_config_updated": (EMOJI_SYSTEM, "Server config updated"),
    # Session
    "session_killed": (EMOJI_DISABLE, "Session killed"),
}


def format_event(
    *,
    action: str,
    username: str | None = None,
    admin_username: str | None = None,
    detail: str | None = None,
    data_limit: int | None = None,
    data_used: int | None = None,
    data_limit_str: str | None = None,
    expires: str | None = None,
    extra: str | None = None,
) -> str | None:
    """Return a MarkdownV2-formatted message for the given event, or None to skip.

    All fields are optional except ``action``.  The function picks an
    emoji and verb from the action map, then appends structured detail.
    """
    emoji, verb = _ACTION_MAP.get(action, (EMOJI_ERROR, action.replace("_", " ").title()))

    user_part = f" `{_esc(username)}`" if username else ""
    lines = [f"{emoji} *{_esc(verb)}*{user_part}"]

    if admin_username:
        lines.append(f"  by admin `{_esc(admin_username)}`")

    if data_limit_str:
        lines.append(f"  limit {data_limit_str}")
    elif data_limit is not None:
        lines.append(f"  limit {_fmt_bytes(data_limit)}")
    else:
        lines.append("  limit unlimited")

    if data_used is not None and data_limit is not None and data_limit > 0:
        pct = data_used / data_limit * 100
        lines.append(f"  usage {_fmt_bytes(data_used)}/{_fmt_bytes(data_limit)} \\({pct:.0f}%\\)")

    if expires:
        lines.append(f"  expires {_esc(expires)}")

    if detail:
        lines.append(f"  {_esc(detail)}")

    if extra:
        lines.append(f"  {_esc(extra)}")

    return "\n".join(lines)
