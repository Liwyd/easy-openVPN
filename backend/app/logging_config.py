"""Structured JSON logging for enforcement actions and audit events.

Every enforcement action logs a single JSON line that feeds the Telegram bot
(next stage) and any external log aggregator.  The format is:
    {"event": "user_disabled", "user": "alice", "reason": "data_limit", "admin": "bob", "timestamp": "..."}
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import sys


class JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": dt.datetime.now(dt.UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Merge any extra structured fields attached to the record
        if hasattr(record, "event_data"):
            log_entry.update(record.event_data)
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger with JSON output to stderr."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def enforcement_log(
    *,
    event: str,
    username: str,
    admin_username: str = "",
    reason: str = "",
    extra: dict | None = None,
) -> None:
    """Write a structured enforcement log line.

    Used by scheduler jobs and API handlers for every enforcement action.
    """
    data: dict = {"event": event, "user": username, "timestamp": dt.datetime.now(dt.UTC).isoformat()}
    if admin_username:
        data["admin"] = admin_username
    if reason:
        data["reason"] = reason
    if extra:
        data.update(extra)

    record = logging.LogRecord(
        name="enforcement",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="",
        args=(),
        exc_info=None,
    )
    record.event_data = data  # type: ignore[attr-defined]
    logging.getLogger("enforcement").handle(record)
