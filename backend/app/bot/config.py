"""Telegram bot configuration — env defaults overlayed by panel settings.

The panel's Settings > Telegram page writes these values to the DB
(``TelegramConfig`` row) and calls ``set_config`` so the running process
uses them immediately.  When no DB row has been saved yet, the
environment variables (TELEGRAM_ENABLED / TELEGRAM_BOT_TOKEN /
TELEGRAM_ADMIN_CHAT_IDS) provide the defaults.

TELEGRAM_ENABLED is the master switch.  When False (the default), every
function in the bot module is a no-op so the rest of the app is unaffected.
"""

from __future__ import annotations

from decouple import config

# Environment-provided defaults (fallback when no DB row exists yet).
_ENV_ENABLED: bool = config("TELEGRAM_ENABLED", default=False, cast=bool)
_ENV_BOT_TOKEN: str = config("TELEGRAM_BOT_TOKEN", default="")

# Comma-separated list of chat IDs that should receive notifications.
# Accepts negative IDs (group chats) as well as positive ones (private).
_ENV_ADMIN_CHAT_IDS: list[str] = config(
    "TELEGRAM_ADMIN_CHAT_IDS",
    default="",
    cast=lambda v: [s.strip() for s in v.split(",") if s.strip()],
)

# Logger channel — if set, notifications go here instead of individual admins.
_ENV_LOGGER_CHANNEL_ID: int = config("TELEGRAM_LOGGER_CHANNEL_ID", default=0, cast=int)

# Bot API credentials for the interactive bot to authenticate to the panel.
_ENV_API_BASE_URL: str = config("TELEGRAM_BOT_API_BASE_URL", default="http://localhost:8000")
_ENV_BOT_ADMIN_USERNAME: str = config("TELEGRAM_BOT_ADMIN_USERNAME", default="")
_ENV_BOT_ADMIN_PASSWORD: str = config("TELEGRAM_BOT_ADMIN_PASSWORD", default="")

# Runtime configuration — the panel writes here and persists it in the DB.
_runtime: dict = {
    "enabled": _ENV_ENABLED,
    "bot_token": _ENV_BOT_TOKEN,
    "admin_chat_ids": list(_ENV_ADMIN_CHAT_IDS),
    "logger_channel_id": _ENV_LOGGER_CHANNEL_ID,
    "api_base_url": _ENV_API_BASE_URL,
    "bot_admin_username": _ENV_BOT_ADMIN_USERNAME,
    "bot_admin_password": _ENV_BOT_ADMIN_PASSWORD,
}


def get_config() -> dict:
    """Return the current runtime Telegram configuration."""
    return _runtime


def set_config(*, enabled: bool, bot_token: str, admin_chat_ids: list[str]) -> None:
    """Replace the runtime config (called by the panel Settings API)."""
    _runtime["enabled"] = bool(enabled)
    _runtime["bot_token"] = bot_token.strip()
    _runtime["admin_chat_ids"] = [
        str(x).strip() for x in (admin_chat_ids or []) if str(x).strip()
    ]


def reset_to_env() -> None:
    """Restore the environment defaults (used by tests / startup fallback)."""
    set_config(
        enabled=_ENV_ENABLED,
        bot_token=_ENV_BOT_TOKEN,
        admin_chat_ids=list(_ENV_ADMIN_CHAT_IDS),
    )
    _runtime["logger_channel_id"] = _ENV_LOGGER_CHANNEL_ID
    _runtime["api_base_url"] = _ENV_API_BASE_URL
    _runtime["bot_admin_username"] = _ENV_BOT_ADMIN_USERNAME
    _runtime["bot_admin_password"] = _ENV_BOT_ADMIN_PASSWORD


# Convenience helpers -------------------------------------------------

def is_configured() -> bool:
    """Return True only when all three required values are present."""
    return bool(
        _runtime["enabled"] and _runtime["bot_token"] and _runtime["admin_chat_ids"]
    )


def get_bot_token() -> str:
    """Return the current bot token."""
    return _runtime["bot_token"]


def get_admin_chat_ids() -> list[str]:
    """Return the list of admin chat IDs as strings."""
    return _runtime["admin_chat_ids"]


def get_logger_channel_id() -> int:
    """Return the logger channel ID (0 if not configured)."""
    return _runtime.get("logger_channel_id", 0)


def get_api_base_url() -> str:
    """Return the FastAPI base URL for bot-to-panel communication."""
    return _runtime.get("api_base_url", "http://localhost:8000")


def get_bot_credentials() -> tuple[str, str]:
    """Return (username, password) for the bot's API admin account."""
    return (
        _runtime.get("bot_admin_username", ""),
        _runtime.get("bot_admin_password", ""),
    )
