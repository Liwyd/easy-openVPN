"""enforce_limits_job — Periodic enforcement of quotas, expiry, and time windows.

Runs every ~60s.  For every active user:
- data_used >= data_limit → set status 'limited', kill + disable
- now > expire_at → set status 'expired', kill + disable
- current time-of-day outside time_window → kill session (kick only,
  do NOT mark disabled — they reconnect once back in window)

User limit vs admin allocation limit are kept clearly separate:
disabling a user for going over their personal quota does NOT
silently mark the whole admin as over quota.
"""

from __future__ import annotations

import datetime as dt
import logging

from app.config import OPENVPN_MANAGEMENT_SOCKET
from app.logging_config import enforcement_log
from app.models.admin import Admin
from app.models.user import User, UserStatus
from app.services.vpn_bridge import disable_client, kill_client_session

logger = logging.getLogger(__name__)


def _is_in_time_window(user: User) -> bool:
    """Check if current time is within the user's time window."""
    if user.time_window_start is None or user.time_window_end is None:
        return True  # No window configured → always allowed

    now = dt.datetime.now(dt.UTC).time()
    start = user.time_window_start
    end = user.time_window_end

    if start <= end:
        # Same-day window, e.g. 08:00-22:00
        return start <= now <= end
    else:
        # Overnight window, e.g. 22:00-06:00
        return now >= start or now <= end


def enforce_limits_job() -> None:
    """Enforce data limits, expiry, and time windows for all active users.

    Designed to be called by APScheduler's BackgroundScheduler.
    Each invocation creates its own DB session.
    """
    import app.db as _db

    db = _db.SessionLocal()
    try:
        # Query all users that are not revoked and not manually disabled
        # (i.e. status is active or limited — expired users stay expired)
        users = (
            db.query(User)
            .filter(
                User.revoked.is_(False),
                User.status.in_([UserStatus.ACTIVE, UserStatus.LIMITED]),
            )
            .all()
        )

        for user in users:
            admin = db.query(Admin).filter(Admin.id == user.admin_id).first()
            admin_username = admin.username if admin else ""

            # --- Data limit enforcement ---
            if user.data_limit is not None and user.data_used >= user.data_limit:
                if user.status != UserStatus.LIMITED:
                    user.status = UserStatus.LIMITED
                    if user.common_name:
                        kill_client_session(user.common_name, OPENVPN_MANAGEMENT_SOCKET)
                        disable_client(user.common_name, management_socket=OPENVPN_MANAGEMENT_SOCKET)
                    enforcement_log(
                        event="user_disabled",
                        username=user.username,
                        admin_username=admin_username,
                        reason="data_limit",
                    )
                    logger.info(
                        "User '%s' disabled: data_used (%d) >= data_limit (%d)",
                        user.username, user.data_used, user.data_limit,
                    )
                continue  # Already handled — skip further checks for this user

            # --- Expiry enforcement ---
            if user.expire_at is not None:
                now = dt.datetime.now(dt.UTC)
                expire = user.expire_at
                # Ensure both are timezone-aware for comparison
                if expire.tzinfo is None:
                    expire = expire.replace(tzinfo=dt.UTC)
                if now > expire:
                    if user.status != UserStatus.EXPIRED:
                        user.status = UserStatus.EXPIRED
                        if user.common_name:
                            kill_client_session(user.common_name, OPENVPN_MANAGEMENT_SOCKET)
                            disable_client(user.common_name, management_socket=OPENVPN_MANAGEMENT_SOCKET)
                        enforcement_log(
                            event="user_expired",
                            username=user.username,
                            admin_username=admin_username,
                            reason="expire_at",
                        )
                        logger.info(
                            "User '%s' expired: now=%s > expire_at=%s",
                            user.username, now.isoformat(), expire.isoformat(),
                        )
                    continue

            # --- Time window enforcement (kick only, no disable) ---
            if not _is_in_time_window(user):
                if user.common_name:
                    kill_client_session(user.common_name, OPENVPN_MANAGEMENT_SOCKET)
                enforcement_log(
                    event="user_kicked",
                    username=user.username,
                    admin_username=admin_username,
                    reason="time_window",
                )
                logger.info(
                    "User '%s' kicked: outside time window (%s-%s)",
                    user.username,
                    user.time_window_start,
                    user.time_window_end,
                )

        db.commit()
    except Exception:
        db.rollback()
        logger.warning("enforce_limits_job failed", exc_info=True)
    finally:
        db.close()
