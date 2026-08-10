"""sync_usage_job — Periodic usage synchronization from OpenVPN management interface.

Polls the management interface every ~45s, diffs byte counters against
the last known snapshot per user, writes UsageLog rows, and updates
User.data_used + owning Admin.data_used.

Counting rules:
- Snapshot entries are keyed by common_name and hold
  (bytes_received, bytes_sent, connected_since) of the LAST observed
  session for that client.
- A client whose counters went DOWN (OpenVPN resets per-session
  counters on reconnect/server restart) OR whose `connected_since`
  timestamp changed is treated as a NEW session: its full current
  counters are counted.  Without the timestamp check, a reconnect that
  already outgrew the old baseline would only be counted as a partial
  delta (undercount).
- The FIRST observation of a common_name within this process is used as
  a baseline and counts nothing.  This is critical: a backend restart
  wipes the in-memory snapshot, and re-counting a still-running
  session's full counter would DOUBLE user usage.  Seeding the baseline
  instead ensures only freshly observed traffic is accumulated.

Thread safety: a module-level Lock prevents concurrent overlapping runs.
If the previous invocation is still running, the new invocation is
skipped entirely (APScheduler's max_instances=1 also helps, but the
lock is a defense-in-depth measure).

Writer race safety: User.data_used is incremented with an atomic
``data_used = data_used + delta`` SQL UPDATE, so a concurrent usage
reset (admin reset-usage endpoint, periodic quota reset job) cannot be
lost to a stale read-modify-write.
"""

from __future__ import annotations

import logging
import threading

from app.config import OPENVPN_MANAGEMENT_SOCKET
from app.models.admin import Admin
from app.models.usage_log import UsageLog
from app.models.user import User
from app.services.quota import recalculate_admin_data_used
from app.services.vpn_bridge import get_live_status

logger = logging.getLogger(__name__)

# Defense-in-depth mutex — prevents concurrent overlapping runs even if
# APScheduler's max_instances setting is bypassed or misconfigured.
_job_lock = threading.Lock()

# In-memory snapshot of last known per-client state.
# Key: common_name, Value: (bytes_received, bytes_sent, connected_since)
# NOTE: this lives in process memory on purpose so that a backend restart
# safely re-baselines every connected client instead of re-counting their
# whole session (see module docstring).  Deployment uses a single
# uvicorn worker, so the in-memory state is unambiguous; multi-worker
# deployments would need this persisted in the DB instead.
_last_snapshot: dict[str, tuple[int, int, str]] = {}


def sync_usage_job() -> None:
    """Poll live status, diff counters, update DB.

    Designed to be called by APScheduler's BackgroundScheduler.
    Each invocation creates its own DB session and commits per-user.
    """
    if not _job_lock.acquire(blocking=False):
        logger.debug("sync_usage_job: previous run still in progress, skipping")
        return

    try:
        _sync_usage_job_inner()
    finally:
        _job_lock.release()


def _is_new_session(last_rx: int, last_tx: int, last_session: str, rx: int, tx: int, session: str) -> bool:
    """Return True if the client's counters refer to a brand-new session.

    A new session is detected when either:
    - the byte counters went backwards (OpenVPN resets them per session
      on reconnect or server restart), or
    - the Connected Since timestamp differs from the last one we saw
      (catches reconnects where the new session has already outgrown the
      old baseline — a plain counter comparison would undercount).
    """
    if rx < last_rx or tx < last_tx:
        return True
    return bool(session and last_session and session != last_session)


def _sync_usage_job_inner() -> None:
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
        session = client.get("connected_since", "") or ""

        prev = _last_snapshot.get(cn)

        # First observation in this process — seed a baseline and count
        # nothing.  A backend restart would otherwise re-count the client's
        # entire (already accumulated) session, inflating their usage.
        if prev is None:
            logger.debug(
                "Seeding baseline for '%s' (rx=%d, tx=%d): previous traffic untracked in this process",
                cn, rx, tx,
            )
            _last_snapshot[cn] = (rx, tx, session)
            continue

        last_rx, last_tx, last_session = prev

        # Counter reset / reconnect — treat as a new session baseline and
        # count its full current totals.
        if _is_new_session(last_rx, last_tx, last_session, rx, tx, session):
            logger.info(
                "New session detected for '%s' (rx: %d->%d, tx: %d->%d). "
                "Counting full session totals.",
                cn, last_rx, rx, last_tx, tx,
            )
            delta_rx = rx
            delta_tx = tx
        else:
            delta_rx = rx - last_rx
            delta_tx = tx - last_tx

        _last_snapshot[cn] = (rx, tx, session)

        # Skip if no actual traffic delta (avoids spurious DB writes)
        if delta_rx == 0 and delta_tx == 0:
            continue

        db = _db.SessionLocal()
        try:
            # Find the user by common_name
            user = db.query(User).filter(User.common_name == cn).first()
            if user is None:
                continue
            if user.revoked:
                continue

            # Atomically accumulate usage — evaluated by the DB as
            # `data_used = data_used + delta`, so a concurrent usage reset
            # cannot be clobbered by a stale read-modify-write.
            db.query(User).filter(User.id == user.id).update(
                {User.data_used: User.data_used + delta_rx + delta_tx},
                synchronize_session=False,
            )

            # Write usage log entry
            db.add(UsageLog(
                user_id=user.id,
                bytes_sent=delta_tx,
                bytes_received=delta_rx,
            ))

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
