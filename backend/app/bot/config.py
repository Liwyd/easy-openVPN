"""Telegram bot configuration — loaded from environment variables.

TELEGRAM_ENABLED is the master switch.  When False (the default), every
function in the bot module is a no-op so the rest of the app is unaffected.
"""

from __future__ import annotations

from decouple import config

TELEGRAM_ENABLED: bool = config("TELEGRAM_ENABLED", default=False, cast=bool)

TELEGRAM_BOT_TOKEN: str = config("TELEGRAM_BOT_TOKEN", default="")

# Comma-separated list of chat IDs that should receive notifications.
# Accepts negative IDs (group chats) as well as positive ones (private).
TELEGRAM_ADMIN_CHAT_IDS: list[str] = config(
    "TELEGRAM_ADMIN_CHAT_IDS",
    default="",
    cast=lambda v: [s.strip() for s in v.split(",") if s.strip()],
)

# Convenience helpers -------------------------------------------------

def is_configured() -> bool:
    """Return True only when all three required values are present."""
    return bool(TELEGRAM_ENABLED and TELEGRAM_BOT_TOKEN and TELEGRAM_ADMIN_CHAT_IDS)
