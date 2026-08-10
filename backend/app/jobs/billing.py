"""Billing cron job — daily debt calculation with anti-gaming.

Runs once per day.  For each non-sudo admin with pricing set:
  1. Calculates debt from ALL users (including revoked)
  2. Volumed users: sum of data_limit × price_per_gb
  3. Unlimited users: user-months × price_per_user
  4. Creates incremental billing records for new charges
  5. Updates admin.debt (charges only go up, settlements go down)

Anti-gaming: counts ALL users ever created, including revoked ones.
Deleting and recreating a user does not reset the billing clock.
"""

from __future__ import annotations

import datetime as dt
import logging
import math

from sqlalchemy import func

from app.db import SessionLocal
from app.models.admin import Admin
from app.models.billing import BillingRecord, BillingType
from app.models.user import User

logger = logging.getLogger(__name__)


def _calc_user_months(user: User, now: dt.datetime) -> int:
    """How many full months this user has existed (minimum 1)."""
    created = user.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=dt.UTC)
    days = (now - created).days
    return max(1, math.ceil(days / 30))


def _process_admin(admin: Admin, db) -> None:
    """Calculate and record billing for a single admin."""
    now = dt.datetime.now(dt.UTC)

    # --- Volumed users (have data_limit) ---
    volumed_total_bytes = (
        db.query(func.coalesce(func.sum(User.data_limit), 0))
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
    total_user_months = sum(_calc_user_months(u, now) for u in unlimited_users)

    # --- Calculate charges ---
    volumed_charge = 0.0
    if admin.price_per_gb and volumed_total_bytes > 0:
        volumed_charge = round((volumed_total_bytes / (1024 ** 3)) * admin.price_per_gb, 6)

    unlimited_charge = 0.0
    if admin.price_per_user and total_user_months > 0:
        unlimited_charge = round(total_user_months * admin.price_per_user, 6)

    total_new_charge = round(volumed_charge + unlimited_charge, 6)

    # --- Create billing records for the delta ---
    # Only create records if there are actual charges
    if volumed_charge > 0:
        vol_desc = f"{volumed_total_bytes / (1024 ** 3):.2f} GB × ${admin.price_per_gb:.2f}"
        record = BillingRecord(
            admin_id=admin.id,
            type=BillingType.TRAFFIC_CHARGE,
            amount=volumed_charge,
            description=vol_desc,
        )
        db.add(record)

    if unlimited_charge > 0:
        user_desc = f"{total_user_months} user-months × ${admin.price_per_user:.2f}"
        record = BillingRecord(
            admin_id=admin.id,
            type=BillingType.USER_CHARGE,
            amount=unlimited_charge,
            description=user_desc,
        )
        db.add(record)

    # --- Update debt (charges only go up) ---
    if total_new_charge > admin.debt:
        admin.debt = total_new_charge

    db.commit()
    logger.info(
        "Billing processed for admin %s: volumed=$%.2f unlimited=$%.2f total=$%.2f debt=$%.2f",
        admin.username, volumed_charge, unlimited_charge, total_new_charge, admin.debt,
    )


def billing_job() -> None:
    """Daily billing job — calculates debt for all non-sudo admins with pricing."""
    db = SessionLocal()
    try:
        admins = (
            db.query(Admin)
            .filter(
                Admin.is_sudo.is_(False),
                (Admin.price_per_user.isnot(None)) | (Admin.price_per_gb.isnot(None)),
            )
            .all()
        )

        for admin in admins:
            try:
                _process_admin(admin, db)
            except Exception:
                logger.exception("Billing failed for admin %s", admin.username)
                db.rollback()

        if admins:
            logger.info("Billing job completed for %d admins", len(admins))
    finally:
        db.close()
