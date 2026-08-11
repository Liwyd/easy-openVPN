"""Scheduled backup job — runs daily at the configured hour/minute (UTC).

The job runs on a 60-second interval and decides itself whether the
configured time has arrived, so schedule changes take effect instantly
without rescheduling the APScheduler job.  When ``send_to_telegram`` is
enabled it delivers the archive to Telegram right after creating it, and
old archives are pruned to ``keep_count``.
"""

from __future__ import annotations

import datetime as dt
import logging

from app.db import SessionLocal
from app.models.backup_config import get_backup_config
from app.services.backup import create_backup, prune_backups

logger = logging.getLogger(__name__)

# Upper bound so a hiccup can't produce two backups in quick succession.
_MIN_MINUTES_BETWEEN_RUNS = 5


def backup_job() -> None:
    """Scheduled-entry point.  No-op unless the schedule says it's time."""
    db = SessionLocal()
    try:
        cfg = get_backup_config(db)
        if not cfg.enabled:
            return

        now = dt.datetime.now(dt.UTC)

        # Run exactly once per scheduled day.
        if cfg.last_run_at is not None and cfg.last_run_at.date() == now.date():
            return

        if now.hour != cfg.schedule_hour or now.minute != cfg.schedule_minute:
            return

        from app.bot.backup import notify_backup

        meta = create_backup(db)

        cfg.last_run_at = now
        cfg.last_backup_file = meta["filename"]
        db.commit()

        if cfg.send_to_telegram:
            notify_backup(meta)

        removed = prune_backups(cfg.keep_count)
        if removed:
            logger.info("Scheduled backup pruned %d old archive(s)", removed)
        logger.info("Scheduled backup created: %s", meta["filename"])
    except Exception:
        logger.exception("Scheduled backup job failed")
    finally:
        db.close()
