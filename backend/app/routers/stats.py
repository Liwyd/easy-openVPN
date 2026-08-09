"""Stats API — aggregated dashboard data for the frontend.

GET /api/stats/summary → total users, admins, traffic across the panel
GET /api/stats/usage-over-time → daily aggregated traffic for charts
GET /api/stats/top-users → top users by usage
GET /api/stats/status-breakdown → counts per user status
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.admin import Admin
from app.models.usage_log import UsageLog
from app.models.user import User, UserStatus
from app.services.auth import get_current_admin

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
