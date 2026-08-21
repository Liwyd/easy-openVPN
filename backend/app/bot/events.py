"""Event categories and the lightweight event bus.

The service layer calls ``emit(...)`` after a state change.  The bot
module decides whether to forward the event to Telegram based on the
category tag:

* ``ENFORCEMENT`` — quota / expiry driven status changes  → send
* ``ADMIN_ACTION`` — explicit admin CRUD operations        → send
* ``SYSTEM``       — server config changes                 → send
* ``SYNC``         — periodic usage-sync ticks             → SILENCED

When the interactive bot is running, notifications are sent through
the bot instance (which has richer formatting and inline keyboards).
When the bot is not running, falls back to raw httpx sends.
"""

from __future__ import annotations

import enum
import logging

from app.bot.config import is_configured
from app.bot.formatter import format_event

logger = logging.getLogger(__name__)


class EventCategory(str, enum.Enum):
    ENFORCEMENT = "enforcement"
    ADMIN_ACTION = "admin_action"
    SYSTEM = "system"
    SYNC = "sync"


def emit(
    *,
    category: EventCategory,
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
) -> None:
    """Emit an event.  Filters out SYNC events, then sends to Telegram.

    This function is fire-and-forget: any Telegram failure is logged at
    WARNING level and silently swallowed.
    """
    if not is_configured():
        logger.debug("Telegram not configured — skipping notification for %s", action)
        return

    if category == EventCategory.SYNC:
        logger.debug("SYNC event %s — suppressed from Telegram", action)
        return

    text = format_event(
        action=action,
        username=username,
        admin_username=admin_username,
        belongs_to=belongs_to,
        detail=detail,
        data_limit=data_limit,
        data_used=data_used,
        data_limit_str=data_limit_str,
        expires=expires,
        extra=extra,
    )
    if text is None:
        return

    # Try to send through the interactive bot first (richer formatting),
    # fall back to raw httpx if the bot is not running.
    try:
        from app.bot import get_application
        app = get_application()
        if app is not None:
            from app.bot import send_notification
            send_notification(text)
            return
    except Exception:
        pass

    from app.bot.client import send_message_plain
    try:
        send_message_plain(text)
    except Exception:
        logger.warning("Failed to send Telegram notification for %s", action, exc_info=True)
