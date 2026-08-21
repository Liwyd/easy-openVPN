"""Notification report system — Marzban-style notification messages.

Generates formatted notification messages identical to Marzban's
``app/telegram/handlers/report.py`` for all user lifecycle events.
Used by the event bus and direct bot operations.
"""

from __future__ import annotations

from app.bot.utils.shared import fmt_bytes


def report_new_user(
    username: str,
    by: str,
    expire_date: str | None = None,
    data_limit: int | None = None,
    admin: str | None = None,
) -> str:
    """Generate new user created notification — Marzban exact format."""
    return f"""\
🆕 <b>#Created</b>
➖➖➖➖➖➖➖➖➖
<b>Username :</b> <code>{username}</code>
<b>Traffic Limit :</b> <code>{fmt_bytes(data_limit) if data_limit else "Unlimited"}</code>
<b>Expire Date :</b> <code>{expire_date or "Never"}</code>
➖➖➖➖➖➖➖➖➖
<b>Belongs To :</b> <code>{admin or "-"}</code>
<b>By :</b> <b>#{by}</b>"""


def report_user_modification(
    username: str,
    by: str,
    data_limit: int | None = None,
    expire_date: str | None = None,
    admin: str | None = None,
) -> str:
    """Generate user modification notification — Marzban exact format."""
    return f"""\
✏️ <b>#Modified</b>
➖➖➖➖➖➖➖➖➖
<b>Username :</b> <code>{username}</code>
<b>Traffic Limit :</b> <code>{fmt_bytes(data_limit) if data_limit else "Unlimited"}</code>
<b>Expire Date :</b> <code>{expire_date or "Never"}</code>
➖➖➖➖➖➖➖➖➖
<b>Belongs To :</b> <code>{admin or "-"}</code>
<b>By :</b> <b>#{by}</b>"""


def report_user_deletion(username: str, by: str, admin: str | None = None) -> str:
    """Generate user deletion notification — Marzban exact format."""
    return f"""\
🗑 <b>#Deleted</b>
➖➖➖➖➖➖➖➖➖
<b>Username</b> : <code>{username}</code>
➖➖➖➖➖➖➖➖➖
<b>Belongs To :</b> <code>{admin or "-"}</code>
<b>By</b> : <b>#{by}</b>"""


def report_status_change(username: str, status: str, admin: str | None = None) -> str:
    """Generate status change notification — Marzban exact format."""
    _status = {
        "active": "✅ <b>#Activated</b>",
        "disabled": "❌ <b>#Disabled</b>",
        "limited": "🪫 <b>#Limited</b>",
        "expired": "🕔 <b>#Expired</b>",
    }
    return f"""\
{_status.get(status, status)}
➖➖➖➖➖➖➖➖➖
<b>Username</b> : <code>{username}</code>
<b>Belongs To :</b> <code>{admin or "-"}</code>"""


def report_user_usage_reset(username: str, by: str, admin: str | None = None) -> str:
    """Generate usage reset notification — Marzban exact format."""
    return f"""\
🔁 <b>#Reset</b>
➖➖➖➖➖➖➖➖➖
<b>Username</b> : <code>{username}</code>
➖➖➖➖➖➖➖➖➖
<b>Belongs To :</b> <code>{admin or "-"}</code>
<b>By</b> : <b>#{by}</b>"""


def report_user_data_reset_by_next(
    username: str,
    data_limit: int | None = None,
    expire_date: str | None = None,
) -> str:
    """Generate auto-reset notification — Marzban exact format."""
    return f"""\
🔁 <b>#AutoReset</b>
➖➖➖➖➖➖➖➖➖
<b>Username :</b> <code>{username}</code>
<b>Traffic Limit :</b> <code>{fmt_bytes(data_limit) if data_limit else "Unlimited"}</code>
<b>Expire Date :</b> <code>{expire_date or "Never"}</code>
➖➖➖➖➖➖➖➖➖"""


def report_user_subscription_revoked(username: str, by: str, admin: str | None = None) -> str:
    """Generate subscription revoked notification — Marzban exact format."""
    return f"""\
🔁 <b>#Revoked</b>
➖➖➖➖➖➖➖➖➖
<b>Username</b> : <code>{username}</code>
➖➖➖➖➖➖➖➖➖
<b>Belongs To :</b> <code>{admin or "-"}</code>
<b>By</b> : <b>#{by}</b>"""


def report_login(username: str, password: str, client_ip: str, status: str) -> str:
    """Generate login notification — Marzban exact format."""
    return f"""\
🔐 <b>#Login</b>
➖➖➖➖➖➖➖➖➖
<b>Username</b> : <code>{username}</code>
<b>Password</b> : <code>{password}</code>
<b>Client ip </b>: <code>{client_ip}</code>
➖➖➖➖➖➖➖➖➖
<b>login status </b>: <code>{status}</code>"""
