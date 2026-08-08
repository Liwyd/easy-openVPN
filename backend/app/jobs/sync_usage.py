"""sync_usage_job — Periodic usage synchronization from OpenVPN management interface.

Polls the management interface every ~45s, diffs byte counters against
the last known snapshot per user, writes UsageLog rows, and updates
User.data_used + owning Admin.data_used (all in one transaction per
user to keep the hierarchy consistent).

Handles counter resets (OpenVPN resets counters on reconnect) by
detecting a decrease and treating it as a new session baseline instead
of a negative delta.
"""

from __future__ import annotations

import logging

from app.config import OPENVPN_MANAGEMENT_SOCKET
from app.models.admin import Admin
from app.models.usage_log import UsageLog
from app.models.user import User
from app.services.quota import recalculate_admin_data_used
from app.services.vpn_bridge import get_live_status

logger = logging.getLogger(__name__)

# In-memory snapshot of last known byte counters per CN.
# Key: common_name, Value: (bytes_received, bytes_sent)
_last_snapshot: dict[str, tuple[int, int]] = {}


def sync_usage_job() -> None:
    """Poll live status, diff counters, update DB.

    Designed to be called by APScheduler's BackgroundScheduler.
    Each invocation creates its own DB session and commits per-user.
    """
    import app.db as _db

    try:
        clients = get_live_status(OPENVPN_MANAGEMENT_SOCKET)
    except Exception:
        logger.warning("Failed to get live status from management interface", exc_info=True)
        return

    # Build a set of currently connected CNs for snapshot cleanup
    connected_cns = {c["common_name"] for c in clients}

    for client in clients:
        cn = client["common_name"]
        rx = client["bytes_received"]
        tx = client["bytes_sent"]

        last_rx, last_tx = _last_snapshot.get(cn, (0, 0))

        # Handle counter reset: if current < last, OpenVPN restarted
        # and counters rolled over.  Treat as new session baseline.
        if rx < last_rx or tx < last_tx:
            logger.info(
                "Counter reset detected for '%s' (rx: %d->%d, tx: %d->%d). "
                "Treating as new session baseline.",
                cn, last_rx, rx, last_tx, tx,
            )
            delta_rx = rx
            delta_tx = tx
        else:
            delta_rx = rx - last_rx
            delta_tx = tx - last_tx

        _last_snapshot[cn] = (rx, tx)

        # Skip if no actual traffic delta (avoids spurious DB writes)
        if delta_rx == 0 and delta_tx == 0:
            continue

        db = _db.SessionLocal()
        try:
            # Find the user by common_name with row-level locking
            user = db.query(User).filter(User.common_name == cn).first()
            if user is None:
                continue
            if user.revoked:
                continue

            # Update user's cumulative usage
            user.data_used += delta_rx + delta_tx

            # Write usage log entry
            usage_log = UsageLog(
                user_id=user.id,
                bytes_sent=delta_tx,
                bytes_received=delta_rx,
            )
            db.add(usage_log)

            # Recalculate the owning admin's data_used in the same transaction
            admin = db.query(Admin).filter(Admin.id == user.admin_id).first()
            if admin is not None:
                recalculate_admin_data_used(admin, db)

            db.commit()
        except Exception:
            db.rollback()
            logger.warning("Failed to sync usage for CN '%s'", cn, exc_info=True)
        finally:
            db.close()

    # Clean up snapshot entries for clients that are no longer connected
    stale_cns = set(_last_snapshot.keys()) - connected_cns
    for cn in stale_cns:
        del _last_snapshot[cn]
