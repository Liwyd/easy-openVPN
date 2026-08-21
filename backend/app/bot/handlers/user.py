"""User-facing bot commands — /usage.

Mirrors Marzban's ``app/telegram/handlers/user.py`` exactly.
Available to any user (no admin check).
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.api_client import get_client
from app.bot.utils.shared import STATUSES, fmt_bytes


async def usage_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /usage <username> — show user status summary."""
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: `/usage <username>`", parse_mode="MarkdownV2"
        )
        return

    username = args[0]
    client = get_client()
    try:
        user = client.get_user(username)
    except Exception:
        await update.message.reply_text("No user found with this username")
        return

    status = user.get("status", "active")
    status_emoji = STATUSES.get(status, "?")
    data_limit = user.get("data_limit")
    data_used = user.get("data_used", 0)
    expire_at = user.get("expire_at")

    from datetime import datetime

    if expire_at:
        if isinstance(expire_at, str):
            try:
                expire_dt = datetime.fromisoformat(expire_at.replace("Z", "+00:00"))
                expire_str = expire_dt.strftime("%Y-%m-%d")
                days_left = (expire_dt - datetime.now(expire_dt.tzinfo)).days
            except (ValueError, TypeError):
                expire_str = "Never"
                days_left = "-"
        else:
            expire_str = "Never"
            days_left = "-"
    else:
        expire_str = "Never"
        days_left = "-"

    text = f"""\
┌─{status_emoji} <b>Status:</b> <code>{status.title()}</code>
│          └─<b>Username:</b> <code>{user['username']}</code>
│
├─🔋 <b>Data limit:</b> <code>{fmt_bytes(data_limit) if data_limit else 'Unlimited'}</code>
│          └─<b>Data Used:</b> <code>{fmt_bytes(data_used) if data_used else "-"}</code>
│
└─📅 <b>Expiry Date:</b> <code>{expire_str}</code>
            └─<b>Days left:</b> <code>{days_left}</code>"""

    await update.message.reply_text(text, parse_mode="HTML")
