"""Billing service — debt computation shared by the billing router and daily job.

The debt is NOT stored-and-stale: it is derived on demand from two
sources of truth:
- the current created-volume charge (sum of users' data_limit ×
  price_per_gb + unlimited user-months × price_per_user), and
- the settlement ledger (negative-amount SETTLEMENT records).

This means the sudo billing screen reflects the charge for volume
*created* (not consumed) immediately, without waiting for the daily
cron.  The daily job still writes TRAFFIC_CHARGE / USER_CHARGE records
as an audit trail.
"""

from __future__ import annotations

import datetime as dt
import math

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.admin import Admin
from app.models.billing import BillingRecord, BillingType
from app.models.user import User


def calc_user_months(user: User, now: dt.datetime) -> int:
    """How many full months this user has existed (minimum 1)."""
    created = user.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=dt.UTC)
    days = (now - created).days
    return max(1, math.ceil(days / 30))


def calc_charges_for_admin(admin: Admin, db: Session) -> dict:
    """Current charges based on CREATED volume, not consumed usage.

    Volumed users (data_limit set) are charged on the sum of their
    data_limit — the volume allocated at creation.  Unlimited users
    (no data_limit) are charged per user-month.
    """
    now = dt.datetime.now(dt.UTC)

    # --- Volumed users (have data_limit) ---
    volumed_total_bytes = (
        db.query(func.coalesce(func.sum(User.data_limit), 0))
        .filter(User.admin_id == admin.id, User.data_limit.isnot(None))
        .scalar()
        or 0
    )
    volumed_user_count = (
        db.query(func.count(User.id))
        .filter(User.admin_id == admin.id, User.data_limit.isnot(None))
        .scalar()
        or 0
    )

    # --- Unlimited users (no data_limit) ---
    unlimited_users = (
        db.query(User)
        .filter(User.admin_id == admin.id, User.data_limit.is_(None))
        .all()
    )
    unlimited_user_count = len(unlimited_users)
    total_user_months = sum(calc_user_months(u, now) for u in unlimited_users)

    # --- Charges ---
    volumed_charge = (volumed_total_bytes / (1024 ** 3)) * (admin.price_per_gb or 0) if admin.price_per_gb else 0
    unlimited_charge = total_user_months * (admin.price_per_user or 0) if admin.price_per_user else 0

    return {
        "volumed_total_bytes": volumed_total_bytes,
        "volumed_user_count": volumed_user_count,
        "unlimited_user_count": unlimited_user_count,
        "total_user_months": total_user_months,
        "volumed_charge": volumed_charge,
        "unlimited_charge": unlimited_charge,
        "total_charge": volumed_charge + unlimited_charge,
    }


def calculate_admin_debt(admin: Admin, db: Session) -> float:
    """Outstanding debt = current created-volume charge minus settlements.

    Settlements are stored as negative amounts on BillingRecord, so the
    debt is `charge + sum(settlement amounts)`, floored at 0.
    """
    charge = calc_charges_for_admin(admin, db)["total_charge"]
    settled = (
        db.query(func.coalesce(func.sum(BillingRecord.amount), 0))
        .filter(
            BillingRecord.admin_id == admin.id,
            BillingRecord.type == BillingType.SETTLEMENT,
        )
        .scalar()
        or 0
    )
    return max(0.0, round(charge + settled, 6))
