"""Custom filters for the Telegram bot.

IsAdminFilter restricts handlers to configured admin chat IDs only.
"""

from __future__ import annotations

from telegram import Update
from telegram.ext.filters import BaseFilter

from app.bot.config import get_admin_chat_ids


class IsAdminFilter(BaseFilter):
    """Filter that checks if the message originates from a configured admin chat."""

    def filter(self, update: Update) -> bool:
        if update.callback_query:
            return str(update.callback_query.from_user.id) in get_admin_chat_ids()
        if update.message:
            return str(update.message.chat.id) in get_admin_chat_ids()
        return False


is_admin = IsAdminFilter()


def cb_query_equals(text: str):
    """Return a filter matching callback queries with exact data."""
    return lambda query: query.data == text


def cb_query_startswith(text: str):
    """Return a filter matching callback queries whose data starts with text."""
    return lambda query: query.data.startswith(text)
