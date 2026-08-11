"""BackupConfig — single-row table holding scheduled-backup settings.

Stores the schedule (daily hour/minute), whether completed backups should
be delivered to Telegram alongside the running notifications, and how many
archives to retain.  Wired to the APScheduler job in app/jobs/backup.py.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class BackupConfig(Base):
    __tablename__ = "backup_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Master switch — when False the scheduled job is a no-op.
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Daily schedule in UTC.
    schedule_hour: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    schedule_minute: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Deliver the archive to Telegram right after a scheduled backup.
    send_to_telegram: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # How many archives to keep.  0 = keep everything.
    keep_count: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    # Bookkeeping for the scheduler.
    last_run_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    last_backup_file: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


def get_backup_config(db) -> BackupConfig:
    """Return the single BackupConfig row, creating the default if missing."""
    cfg = db.query(BackupConfig).first()
    if cfg is None:
        cfg = BackupConfig(id=1)
        db.add(cfg)
        db.commit()
    return cfg
