"""sync_usage_job — Periodic usage synchronization from the OpenVPN management interface.

Polls the management interface every ~45s, diffs byte counters against
the last known snapshot per user, writes UsageLog rows, and updates
User.data_used + owning Admin.data_used.

Counting model (mirrors the OV-Panel snapshot/delta pattern):
- OpenVPN reports PER-SESSION cumulative byte counters.  They reset to
  0 whenever a client reconnects (or the server restarts) and the client
  disappears from the status entirely on disconnect — only live sessions
  are listed.
- A per-user snapshot (last_rx, last_tx, last_connected_since) is
  persisted on the User row.  The delta between two polls is the bytes
  consumed in that window.  A counter that went DOWN (reconnect / server
  restart) OR a changed connected-since timestamp means a brand-new
  session, whose full current counters are counted.
- The FIRST observation of a user (last_rx IS NULL — a new user, or a
  row that predates this feature) seeds the baseline and counts nothing,
  so an already-running session is never double-counted.
- The snapshot is NEVER cleared on disconnect and survives backend
  restarts because it lives in the DB, not process memory.  Without
  that, a disconnect+reconnect between polls would re-seed the baseline
  and silently drop the entire new session (the classic undercount).

Thread safety: a module-level Lock prevents concurrent overlapping runs.
Writer race safety: User.data_used is incremented with an atomic
``data_used = data_used + delta`` SQL UPDATE, so a concurrent usage
reset (admin reset-usage endpoint) cannot be lost to a stale
read-modify-write.
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


def sync_usage_job() -> None:
    """Poll live status, diff counters, update DB.

    Designed to be called by APScheduler's BackgroundScheduler.
    Each invocation creates its own DB session and commits per-client.
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

    db = _db.SessionLocal()
    try:
        for client in clients:
            try:
                _sync_client(db, client)
                db.commit()
            except Exception:
                db.rollback()
                logger.warning(
                    "Failed to sync usage for CN '%s'",
                    client.get("common_name"),
                    exc_info=True,
                )
    finally:
        db.close()


def _sync_client(db, client: dict) -> None:
    """Apply one client's status row to its User snapshot + usage totals."""
    cn = client["common_name"]
    rx = client["bytes_received"]
    tx = client["bytes_sent"]
    session = client.get("connected_since", "") or ""

    user = db.query(User).filter(User.common_name == cn).first()
    if user is None or user.revoked:
        return

    # First observation of this user in the DB — seed a baseline and
    # count nothing.  A session that was already running before we ever
    # observed it (e.g. created while connected) must not be counted in
    # full; only freshly observed traffic is accumulated from here on.
    if user.last_rx is None:
        logger.debug(
            "Seeding baseline for '%s' (rx=%d, tx=%d): no previous snapshot",
            cn, rx, tx,
        )
        db.query(User).filter(User.id == user.id).update(
            {
                User.last_rx: rx,
                User.last_tx: tx,
                User.last_connected_since: session,
            },
            synchronize_session=False,
        )
        return

    # Counter reset / reconnect — treat as a new session and count its
    # full current totals (OV-Panel's "else: delta = used_bytes").
    if _is_new_session(user.last_rx, user.last_tx, user.last_connected_since or "", rx, tx, session):
        logger.info(
            "New session detected for '%s' (rx: %d->%d, tx: %d->%d). "
            "Counting full session totals.",
            cn, user.last_rx, rx, user.last_tx, tx,
        )
        delta_rx = rx
        delta_tx = tx
    else:
        delta_rx = rx - user.last_rx
        delta_tx = tx - user.last_tx

    # Roll the snapshot forward and bump usage atomically in SQL.  Using
    # `data_used = data_used + delta` means a concurrent usage reset is
    # applied relative to the CURRENT committed value, never resurrected.
    db.query(User).filter(User.id == user.id).update(
        {
            User.data_used: User.data_used + delta_rx + delta_tx,
            User.last_rx: rx,
            User.last_tx: tx,
            User.last_connected_since: session,
        },
        synchronize_session=False,
    )

    if delta_rx == 0 and delta_tx == 0:
        return

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
