"""Quota service — allocation-based guards for the hierarchical admin model.

DESIGN DECISION (allocation-based, not usage-based):
The primary guard at user-creation time checks whether the SUM of
data_limit values assigned to an admin's children (users + sub-admins)
plus the new request fits within the admin's own data_limit.  This is
allocation-based: it caps the total traffic ALLOWED, not the traffic
actually consumed.  This is simpler, predictable, and avoids race
conditions where two concurrent creations both pass a usage check but
together exceed the limit.

Separately, we ALSO track actual usage (data_used) for visibility and
monitoring, but that is NOT the guard at creation time.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.admin import Admin
from app.models.admin_log import AdminAction, AdminLog, TargetType
from app.models.user import User


def _sum_or_zero(query_result):
    """Return query result as int, treating None as 0."""
    return query_result or 0


def can_admin_allocate(admin: Admin, requested_bytes: int, db: Session) -> bool:
    """Check whether *admin* has enough remaining allocatable quota.

    Returns True if:
    - admin.data_limit is None (sudo / unlimited), OR
    - sum(child_admins.data_limit) + sum(users.data_limit) + requested_bytes <= admin.data_limit

    This is the ALLOCATION-based guard — it caps the sum of assigned
    data_limit values, not actual traffic consumed.
    """
    if admin.data_limit is None:
        return True  # sudo / unlimited

    child_admins_limit = _sum_or_zero(
        db.query(func.coalesce(func.sum(Admin.data_limit), 0))
        .filter(Admin.parent_admin_id == admin.id)
        .scalar()
    )

    users_limit = _sum_or_zero(
        db.query(func.coalesce(func.sum(User.data_limit), 0))
        .filter(User.admin_id == admin.id)
        .scalar()
    )

    return (child_admins_limit + users_limit + requested_bytes) <= admin.data_limit


def remaining_allocatable(admin: Admin, db: Session) -> int | None:
    """Return remaining allocatable bytes, or None if unlimited."""
    if admin.data_limit is None:
        return None

    child_admins_limit = _sum_or_zero(
        db.query(func.coalesce(func.sum(Admin.data_limit), 0))
        .filter(Admin.parent_admin_id == admin.id)
        .scalar()
    )

    users_limit = _sum_or_zero(
        db.query(func.coalesce(func.sum(User.data_limit), 0))
        .filter(User.admin_id == admin.id)
        .scalar()
    )

    return admin.data_limit - child_admins_limit - users_limit


def recalculate_admin_data_used(admin: Admin, db: Session) -> None:
    """Recalculate admin.data_used from the sum of its users' data_used."""
    total = db.query(func.sum(User.data_used)).filter(User.admin_id == admin.id).scalar() or 0
    admin.data_used = total


def write_admin_log(
    db: Session,
    admin_id: int,
    action: AdminAction,
    target_type: TargetType,
    target_id: int | None = None,
    detail: str | None = None,
) -> None:
    """Write an audit-log entry.  Called from service layer, not route handlers."""
    log = AdminLog(
        admin_id=admin_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    )
    db.add(log)
