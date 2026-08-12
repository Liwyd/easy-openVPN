"""Stats API — aggregated dashboard data for the frontend.

GET /api/stats/summary → total users, admins, traffic across the panel
GET /api/stats/usage-over-time → daily aggregated traffic for charts
GET /api/stats/top-users → top users by usage
GET /api/stats/status-breakdown → counts per user status
GET /api/stats/system → live CPU, RAM, disk metrics
GET /api/stats/me/usage → current admin's own quota usage
"""

from __future__ import annotations

import datetime as dt
import os
import time

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.admin import Admin
from app.models.usage_log import UsageLog
from app.models.user import User, UserStatus
from app.services.auth import get_current_admin
from app.services.quota import remaining_allocatable

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Return summary stats. Sudo sees global; sub-admins see their own scope."""
    if current_admin.is_sudo:
        total_users = db.query(func.count(User.id)).filter(User.revoked.is_(False)).scalar() or 0
        total_admins = db.query(func.count(Admin.id)).scalar() or 0
        total_traffic = db.query(func.sum(User.data_used)).filter(User.revoked.is_(False)).scalar() or 0
    else:
        total_users = (
            db.query(func.count(User.id))
            .filter(User.admin_id == current_admin.id, User.revoked.is_(False))
            .scalar()
            or 0
        )
        total_admins = (
            db.query(func.count(Admin.id))
            .filter(Admin.parent_admin_id == current_admin.id)
            .scalar()
            or 0
        )
        total_traffic = (
            db.query(func.sum(User.data_used))
            .filter(User.admin_id == current_admin.id, User.revoked.is_(False))
            .scalar()
            or 0
        )

    return {
        "total_users": total_users,
        "total_admins": total_admins,
        "total_traffic_bytes": total_traffic,
    }


@router.get("/usage-over-time")
def get_usage_over_time(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Aggregate UsageLog by day for the last N days.

    For sudo admins, aggregates across all users. For sub-admins, only
    their own users' traffic is included.
    """
    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)

    q = (
        db.query(
            func.date(UsageLog.timestamp).label("day"),
            func.sum(UsageLog.bytes_sent + UsageLog.bytes_received).label("total_bytes"),
        )
        .filter(UsageLog.timestamp >= cutoff)
    )

    if not current_admin.is_sudo:
        user_ids = db.query(User.id).filter(User.admin_id == current_admin.id).subquery()
        q = q.filter(UsageLog.user_id.in_(user_ids))

    rows = (
        q.group_by(func.date(UsageLog.timestamp))
        .order_by(func.date(UsageLog.timestamp))
        .all()
    )

    return [
        {"date": str(row.day), "bytes": row.total_bytes or 0}
        for row in rows
    ]


@router.get("/top-users")
def get_top_users(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Return top users by data_used."""
    q = db.query(User).filter(User.revoked.is_(False))
    if not current_admin.is_sudo:
        q = q.filter(User.admin_id == current_admin.id)

    users = q.order_by(User.data_used.desc()).limit(limit).all()

    return [
        {
            "username": u.username,
            "data_used": u.data_used,
            "data_limit": u.data_limit,
            "status": u.status.value,
        }
        for u in users
    ]


@router.get("/status-breakdown")
def get_status_breakdown(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Return counts per user status."""
    q = db.query(User.status, func.count(User.id)).filter(User.revoked.is_(False))
    if not current_admin.is_sudo:
        q = q.filter(User.admin_id == current_admin.id)

    rows = q.group_by(User.status).all()

    breakdown = {s.value: 0 for s in UserStatus}
    for status, count in rows:
        breakdown[status.value] = count

    return breakdown


def _read_cpu_times() -> tuple[int, int]:
    """Read aggregate CPU idle/total from /proc/stat."""
    try:
        with open("/proc/stat") as f:
            parts = f.readline().split()
        # user nice system idle iowait irq softirq steal
        vals = [int(x) for x in parts[1:9]]
        idle = vals[3] + vals[4]  # idle + iowait
        total = sum(vals)
        return idle, total
    except (OSError, ValueError, IndexError):
        return 0, 0


_prev_idle: int = 0
_prev_total: int = 0
_prev_time: float = 0.0


def _get_cpu_percent() -> float:
    """Sample CPU usage over a short interval (returns 0-100)."""
    global _prev_idle, _prev_total, _prev_time

    idle, total = _read_cpu_times()
    now = time.monotonic()

    if _prev_total == 0 or now - _prev_time < 0.1:
        _prev_idle, _prev_total, _prev_time = idle, total, now
        time.sleep(0.1)
        idle, total = _read_cpu_times()
        now = time.monotonic()

    d_idle = idle - _prev_idle
    d_total = total - _prev_total
    _prev_idle, _prev_total, _prev_time = idle, total, now

    if d_total == 0:
        return 0.0
    return round((1.0 - d_idle / d_total) * 100, 1)


def _get_mem_info() -> dict:
    """Read RAM info from /proc/meminfo."""
    info: dict[str, int] = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                key = parts[0].rstrip(":")
                info[key] = int(parts[1]) * 1024  # kB → bytes
    except (OSError, ValueError, IndexError):
        pass

    total = info.get("MemTotal", 0)
    available = info.get("MemAvailable", 0)
    used = total - available
    return {
        "total_bytes": total,
        "used_bytes": used,
        "available_bytes": available,
        "percent": round((used / total) * 100, 1) if total > 0 else 0,
    }


def _get_disk_info(path: str = "/") -> dict:
    """Get disk usage for the given path."""
    try:
        st = os.statvfs(path)
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        used = total - free
        return {
            "total_bytes": total,
            "used_bytes": used,
            "free_bytes": free,
            "percent": round((used / total) * 100, 1) if total > 0 else 0,
        }
    except OSError:
        return {"total_bytes": 0, "used_bytes": 0, "free_bytes": 0, "percent": 0}


def _get_uptime_seconds() -> float:
    """Read system uptime in seconds from /proc/uptime."""
    try:
        with open("/proc/uptime") as f:
            parts = f.read().split()
        return float(parts[0]) if parts else 0.0
    except (OSError, ValueError, IndexError):
        return 0.0


@router.get("/system")
def get_system_metrics():
    """Return live CPU, RAM, disk, and uptime metrics for the server."""
    cpu = _get_cpu_percent()
    mem = _get_mem_info()
    disk = _get_disk_info()
    return {
        "cpu_percent": cpu,
        "ram": mem,
        "disk": disk,
        "uptime_seconds": _get_uptime_seconds(),
    }


@router.get("/me/usage")
def get_my_usage(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Return quota usage for the current admin (works for both sudo and non-sudo)."""
    child_admins_bytes = (
        db.query(func.sum(Admin.data_used))
        .filter(Admin.parent_admin_id == current_admin.id)
        .scalar()
        or 0
    )
    direct_users_bytes = (
        db.query(func.sum(User.data_used))
        .filter(User.admin_id == current_admin.id)
        .scalar()
        or 0
    )

    remaining = remaining_allocatable(current_admin, db)

    return {
        "admin_id": current_admin.id,
        "username": current_admin.username,
        "data_limit": current_admin.data_limit,
        "data_used": current_admin.data_used,
        "remaining": remaining,
        "child_admins_bytes": child_admins_bytes,
        "direct_users_bytes": direct_users_bytes,
    }
