"""Input validation utilities — username safety, positive integers, sane dates."""

from __future__ import annotations

import re
import datetime as dt

# Username must be safe as an OpenVPN common name AND safe as a filesystem
# path component.  Only alphanumeric, hyphens, and underscores allowed.
# Max 64 chars (matches the DB column size).
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def validate_username(username: str) -> None:
    """Raise ValueError if the username contains unsafe characters.

    Safe characters: alphanumeric, hyphens, underscores only.
    Max 64 characters.  No path traversal sequences (../, ..\\, etc.).
    """
    if not username or not _USERNAME_RE.match(username):
        raise ValueError(
            "Username must be 1-64 characters of alphanumeric, hyphens, or underscores only"
        )


def validate_positive_int(value: int | None, field_name: str) -> None:
    """Raise ValueError if value is not a positive integer."""
    if value is not None and value < 0:
        raise ValueError(f"{field_name} must be non-negative, got {value}")


def validate_sane_datetime(value: dt.datetime | None, field_name: str) -> None:
    """Raise ValueError if the datetime is obviously in the past (> 1 day ago).

    This catches user mistakes like entering 2020 instead of 2026.
    We allow a 1-day grace period for timezone drift and clock skew.
    """
    if value is None:
        return
    now = dt.datetime.now(dt.UTC)
    # Make value timezone-aware if naive
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.UTC)
    # Warn if expiry is more than 1 day in the past
    if value < now - dt.timedelta(days=1):
        raise ValueError(f"{field_name} appears to be in the past: {value.isoformat()}")


def validate_time_window(start: dt.time | None, end: dt.time | None) -> None:
    """Raise ValueError if time_window_start > time_window_end (same-day assumption).

    Note: overnight windows (e.g. 22:00-06:00) are allowed in the DB
    but rejected here for simplicity — the client-connect hook handles
    overnight windows correctly regardless of this validation.
    """
    if start is not None and end is not None:
        if start >= end:
            raise ValueError(
                "time_window_start must be before time_window_end "
                f"(got {start.isoformat()} >= {end.isoformat()})"
            )
