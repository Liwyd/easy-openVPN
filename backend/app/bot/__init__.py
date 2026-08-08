"""Telegram notification bot — send event notifications to admin chat(s).

This is a notification-only module.  It does NOT run a long-polling
loop or webhook server.  Messages are sent synchronously via the
Telegram Bot HTTP API whenever the service layer emits an event.

Configuration (env vars):
    TELEGRAM_ENABLED          — master switch (default: false)
    TELEGRAM_BOT_TOKEN        — BotFather token
    TELEGRAM_ADMIN_CHAT_IDS   — comma-separated chat IDs
"""

from app.bot.events import EventCategory, emit  # noqa: F401
from app.bot.client import send_message  # noqa: F401
from app.bot.formatter import format_event  # noqa: F401
