"""reset_periodic_limits_job — Daily quota reset for periodic users.

Runs daily near midnight (server timezone).  For users with
data_limit_reset_strategy != no_reset, resets data_used to 0 and
re-enables if they were only 'limited' (not 'expired' or manually
'disabled'), on the appropriate cadence (daily/weekly/monthly).

Tracks a `last_reset_at` field to determine when the last reset
happened and whether a reset is due today.

Thread safety: a module-level Lock prevents concurrent overlapping runs.
"""

from __future__ import annotations

import datetime as dt
import logging
import threading

from app.logging_config import enforcement_log
from app.models.admin import Admin
from app.models.user import DataLimitResetStrategy, User, UserStatus
from app.services.quota import recalculate_admin_data_used

logger = logging.getLogger(__name__)

# Defense-in-depth mutex
_job_lock = threading.Lock()


def _is_due(last_reset_at: dt.datetime | None, strategy: DataLimitResetStrategy, now: dt.datetime) -> bool:
    """Check if a reset is due based on the strategy and last reset time."""
    if last_reset_at is None:
        return True  # Never reset before → reset now

    if last_reset_at.tzinfo is None:
        last_reset_at = last_reset_at.replace(tzinfo=dt.UTC)

    if strategy == DataLimitResetStrategy.DAILY:
        # Reset if at least 1 day has passed
        return (now - last_reset_at).total_seconds() >= 86400
    elif strategy == DataLimitResetStrategy.WEEKLY:
        # Reset if at least 7 days have passed
        return (now - last_reset_at).total_seconds() >= 7 * 86400
    elif strategy == DataLimitResetStrategy.MONTHLY:
        # Reset if at least 30 days have passed (simplified; exact month
        # tracking would be more complex but this is pragmatic)
        return (now - last_reset_at).total_seconds() >= 30 * 86400
    return False


def reset_periodic_limits_job() -> None:
    """Reset data_used for users with periodic reset strategies.

    Only resets users who were 'limited' due to data cap, NOT users
    who are 'expired' (hard expiry) or 'disabled' (manual admin action).
    """
    if not _job_lock.acquire(blocking=False):
        logger.debug("reset_periodic_limits_job: previous run still in progress, skipping")
        return

    try:
        _reset_periodic_limits_job_inner()
    finally:
        _job_lock.release()


def _reset_periodic_limits_job_inner() -> None:
    import app.db as _db

    db = _db.SessionLocal()
    try:
        now = dt.datetime.now(dt.UTC)

        # Only target users with periodic reset strategies that are
        # currently in 'limited' status (data cap hit, not expiry/manual)
        users = (
            db.query(User)
            .filter(
                User.revoked.is_(False),
                User.data_limit_reset_strategy.in_([
                    DataLimitResetStrategy.DAILY,
                    DataLimitResetStrategy.WEEKLY,
                    DataLimitResetStrategy.MONTHLY,
                ]),
                User.status == UserStatus.LIMITED,
            )
            .all()
        )

        for user in users:
            if not _is_due(user.last_reset_at, user.data_limit_reset_strategy, now):
                continue

            # Reset usage
            user.data_used = 0
            user.last_reset_at = now

            # Re-enable if they were only limited (not expired or manual)
            if user.status == UserStatus.LIMITED:
                user.status = UserStatus.ACTIVE

            # Recalculate owning admin's data_used
            admin = db.query(Admin).filter(Admin.id == user.admin_id).first()
            if admin is not None:
                recalculate_admin_data_used(admin, db)

            enforcement_log(
                event="usage_reset_periodic",
                username=user.username,
                admin_username=admin.username if admin else "",
                extra={"strategy": user.data_limit_reset_strategy.value},
            )
            logger.info(
                "Reset usage for user '%s' (strategy=%s, last_reset=%s)",
                user.username,
                user.data_limit_reset_strategy.value,
                user.last_reset_at.isoformat() if user.last_reset_at else "never",
            )

        db.commit()
    except Exception:
        db.rollback()
        logger.warning("reset_periodic_limits_job failed", exc_info=True)
    finally:
        db.close()
