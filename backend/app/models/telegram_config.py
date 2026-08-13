"""TelegramConfig — panel-controlled Telegram bot settings (single row).

Stores the bot token, the admin chat IDs that receive notifications, and
the master enabled flag.  Values are written by the Settings page (APIs)
and loaded into ``app.bot.config`` at startup so all notifications use
the panel-managed configuration instead of environment variables only.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TelegramConfig(Base):
    __tablename__ = "telegram_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Master switch — when False no notifications are sent.
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # BotFather token — stored in plaintext so the panel can manage it.
    bot_token: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    # List of chat IDs (private or group) that receive notifications.
    admin_chat_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


def get_telegram_config(db) -> TelegramConfig | None:
    """Return the single TelegramConfig row, or None if never configured."""
    return db.query(TelegramConfig).first()
