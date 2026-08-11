"""Message formatting — pure functions, easy to test without network.

Messages follow the panel's Telegram log style: an emoji header, a light
``➖`` separator, ``field : value`` lines, and a trailing ``Belongs To`` /
``By`` block.  Output is plain text (no Markdown) so it renders verbatim in
Telegram.

Emoji convention (mitagain-style):
    created    = 🆕    modified = ✏️    deleted = 🗑
    limited    = 🪫    expired  = 🕔    disabled = 🔴
    activated  = ✅    kicked   = 🔻    config    = 🛠️
    error      = ⚠️    backup   = 📦
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────
SEP = "\u2796" * 17  # ➖➖➖➖... separator line

EMOJI_CREATE = "\U0001f195"  # 🆕
EMOJI_MODIFY = "\u270f\ufe0f"  # ✏️
EMOJI_DELETE = "\U0001f5d1\ufe0f"  # 🗑
EMOJI_LIMITED = "\U0001faab"  # 🪫
EMOJI_EXPIRED = "\U0001f554"  # 🕔
EMOJI_DISABLE = "\U0001f534"  # 🔴
EMOJI_ENABLE = "\u2705"  # ✅
EMOJI_KICKED = "\U0001f53b"  # 🔻
EMOJI_SYSTEM = "\U0001f6e0\ufe0f"  # 🛠️
EMOJI_ERROR = "\u26a0\ufe0f"  # ⚠️
EMOJI_BACKUP = "\U0001f4e6"  # 📦

# Emoji constants kept for backward compatibility with summary assertions.
EMOJI_ADMIN = EMOJI_SYSTEM


def _fmt_bytes(n: int | None) -> str:
    """Human-readable byte size."""
    if n is None:
        return "Unlimited"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}"
        n /= 1024.0  # type: ignore[assignment]
    return f"{n:.1f} PB"


# ── Action → (emoji, verb) mapping ─────────────────────────────────────
_ACTION_MAP: dict[str, tuple[str, str]] = {
    # User lifecycle
    "user_created": (EMOJI_CREATE, "Created"),
    "user_updated": (EMOJI_MODIFY, "Modified"),
    "user_deleted": (EMOJI_DELETE, "Deleted"),
    "user_disabled_limit": (EMOJI_LIMITED, "Limited"),
    "user_limited": (EMOJI_LIMITED, "Limited"),
    "user_disabled_expired": (EMOJI_EXPIRED, "Expired"),
    "user_expired": (EMOJI_EXPIRED, "Expired"),
    "user_disabled_admin": (EMOJI_DISABLE, "Disabled"),
    "user_enabled": (EMOJI_ENABLE, "Activated"),
    "user_kicked": (EMOJI_KICKED, "Kicked"),
    # Admin lifecycle
    "admin_created": (EMOJI_CREATE, "Created"),
    "admin_deleted": (EMOJI_DELETE, "Deleted"),
    "admin_disabled": (EMOJI_DISABLE, "Disabled"),
    "admin_enabled": (EMOJI_ENABLE, "Activated"),
    "admin_updated": (EMOJI_MODIFY, "Modified"),
    # System
    "server_config_updated": (EMOJI_SYSTEM, "Config Updated"),
    "session_killed": (EMOJI_KICKED, "Kicked"),
}


def _format_lines(lines: list[str]) -> str:
    """Join the header + body with the standard separator layout."""
    return "\n".join(lines)


def format_event(
    *,
    action: str,
    username: str | None = None,
    admin_username: str | None = None,
    belongs_to: str | None = None,
    detail: str | None = None,
    data_limit: int | None = None,
    data_used: int | None = None,
    data_limit_str: str | None = None,
    expires: str | None = None,
    extra: str | None = None,
) -> str | None:
    """Return a plain-text log-style message for the given event, or None to skip.

    All fields are optional except ``action``.  The function picks an emoji
    and verb from the action map, then appends structured ``field : value``
    lines in the panel's Telegram style.
    """
    emoji, verb = _ACTION_MAP.get(action, (EMOJI_ERROR, action.replace("_", " ").title()))

    lines: list[str] = [f"{emoji} #{verb}"]

    if username:
        lines.append(f"Username : {username}")

    if data_limit_str is not None:
        lines.append(f"Traffic Limit : {data_limit_str}")
    elif data_limit is not None:
        lines.append(f"Traffic Limit : {_fmt_bytes(data_limit)}")
    else:
        lines.append("Traffic Limit : Unlimited")

    if data_used is not None and data_limit is not None and data_limit > 0:
        pct = data_used / data_limit * 100
        lines.append(f"Usage : {_fmt_bytes(data_used)}/{_fmt_bytes(data_limit)} ({pct:.0f}%)")

    lines.append(f"Expire Date : {expires if expires else 'Never'}")

    if detail:
        lines.append(detail)

    lines.append(SEP)

    if belongs_to:
        lines.append(f"Belongs To : {belongs_to}")
    if admin_username:
        lines.append(f"By : #{admin_username}")

    if extra:
        lines.append(extra)

    return _format_lines(lines)


def format_backup_info(server_ip: str, filename: str, created_at) -> str:
    """Backup summary message in the panel's exact style."""
    stamp = created_at.strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"📦 Backup Information\n"
        f"🌐 Server IP: {server_ip}\n"
        f"📁 Backup File: {filename}\n"
        f"⏰ Backup Time: {stamp} UTC"
    )
