"""Telegram Bot API HTTP client.

Uses ``httpx`` (already a project dependency) to send messages via the
Telegram Bot API.  This avoids pulling in the heavyweight
``python-telegram-bot`` package — we only need ``sendMessage``.

All calls are synchronous because the FastAPI route handlers that
trigger notifications are themselves synchronous.  The HTTP POST to
Telegram's servers typically completes in < 100 ms.
"""

from __future__ import annotations

import logging
import os

import httpx

from app.bot.config import TELEGRAM_ADMIN_CHAT_IDS, TELEGRAM_BOT_TOKEN

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
_TELEGRAM_DOCUMENT_API = "https://api.telegram.org/bot{token}/sendDocument"


def send_message(text: str, *, parse_mode: str = "MarkdownV2") -> None:
    """Send *text* to every configured Telegram chat.

    Raises on HTTP errors so the caller can decide how to handle them
    (the ``events.emit`` wrapper catches all exceptions).
    """
    url = _TELEGRAM_API.format(token=TELEGRAM_BOT_TOKEN)
    payload: dict = {
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }

    with httpx.Client(timeout=10) as client:
        for chat_id in TELEGRAM_ADMIN_CHAT_IDS:
            payload["chat_id"] = chat_id
            resp = client.post(url, json=payload)
            if resp.status_code != 200:
                logger.warning(
                    "Telegram API returned %d for chat %s: %s",
                    resp.status_code,
                    chat_id,
                    resp.text[:200],
                )


def send_message_plain(text: str) -> None:
    """Send *text* without any parse mode (panel's log/timestamp style)."""
    send_message(text, parse_mode=None)


def send_document(filename: str, file_path: str) -> None:
    """Upload *file_path* to every configured chat as a document.

    Used to deliver backup archives.  Raises on HTTP errors.
    """
    if not file_path or not os.path.exists(file_path):
        raise FileNotFoundError(f"Document not found: {file_path}")
    url = _TELEGRAM_DOCUMENT_API.format(token=TELEGRAM_BOT_TOKEN)
    with httpx.Client(timeout=300) as client:
        for chat_id in TELEGRAM_ADMIN_CHAT_IDS:
            with open(file_path, "rb") as handle:
                resp = client.post(
                    url,
                    data={"chat_id": chat_id, "caption": filename},
                    files={"document": (filename, handle, "application/gzip")},
                )
            if resp.status_code != 200:
                logger.warning(
                    "Telegram sendDocument returned %d for chat %s: %s",
                    resp.status_code,
                    chat_id,
                    resp.text[:200],
                )
