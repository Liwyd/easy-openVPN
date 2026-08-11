"""Telegram delivery of backup archives.

Sends the 📦 Backup Information summary (mitagain-style), then uploads the
archive as a document.  Archives larger than Telegram's 50 MB document cap
are split into ``_part_aa/_part_ab/...`` files and each part is uploaded.
"""

from __future__ import annotations

import datetime as dt
import logging
import pathlib

from app.bot.client import send_document, send_message_plain
from app.bot.config import is_configured
from app.bot.formatter import format_backup_info
from app.services.backup import split_backup

logger = logging.getLogger(__name__)


def notify_backup(meta: dict) -> None:
    """Send the backup info message + the archive document(s) to Telegram."""
    if not is_configured():
        logger.debug("Telegram not configured — skipping backup delivery")
        return

    created_at = dt.datetime.fromisoformat(meta["created_at"])
    text = format_backup_info(
        server_ip=meta.get("server_ip", "Unknown"),
        filename=meta["filename"],
        created_at=created_at,
    )

    path = pathlib.Path(meta["path"])
    try:
        send_message_plain(text)
        for part_name in split_backup(path):
            part_path = path.parent / part_name
            send_document(part_name, str(part_path))
    except Exception:
        logger.warning("Failed to deliver backup to Telegram", exc_info=True)
