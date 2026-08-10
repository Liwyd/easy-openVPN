"""Billing router — debt tracking, settlements, top-ups, and pricing.

GET  /api/billing/summary          — sudo: all admins' billing overview
GET  /api/billing/{admin_id}       — sudo: one admin's records
POST /api/billing/{admin_id}/settle — sudo: settle debt
POST /api/billing/{admin_id}/topup  — sudo: increase capacity
PUT  /api/billing/{admin_id}/pricing — sudo: set prices
GET  /api/billing/me               — any admin: own debt view
"""

from __future__ import annotations

import datetime as dt
import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.bot.events import EventCategory, emit
from app.db import get_db
from app.models.admin import Admin
from app.models.billing import BillingRecord, BillingType
from app.models.user import User
from app.schemas.billing import (
    BillingAdminSummary,
    BillingMeResponse,
    BillingRecordResponse,
    PricingRequest,
    SettleRequest,
    TopUpRequest,
)
from app.services.auth import get_current_admin, get_current_sudo_admin

router = APIRouter(prefix="/api/billing", tags=["billing"])


def _calc_user_months(user: User, now: dt.datetime) -> int:
    """How many full months this user has existed (minimum 1)."""
    created = user.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=dt.UTC)
    days = (now - created).days
    return max(1, math.ceil(days / 30))


def _calc_billing_for_admin(admin: Admin, db: Session) -> dict:
    """Calculate current billing state for an admin (anti-gaming).

    Counts ALL users including revoked.  Volumed users contribute their
    data_limit to a total; unlimited users each contribute user-months.
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
    total_user_months = sum(_calc_user_months(u, now) for u in unlimited_users)

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


# ---------------------------------------------------------------------------
# Sudo endpoints
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=list[BillingAdminSummary])
def get_billing_summary(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """Return billing overview for all non-sudo admins."""
    admins = db.query(Admin).filter(Admin.is_sudo.is_(False)).order_by(Admin.id).all()

    result = []
    for adm in admins:
        billing = _calc_billing_for_admin(adm, db)
        result.append(BillingAdminSummary(
            admin_id=adm.id,
            username=adm.username,
            is_sudo=adm.is_sudo,
            price_per_user=adm.price_per_user,
            price_per_gb=adm.price_per_gb,
            debt=adm.debt,
            data_limit=adm.data_limit,
            data_used=adm.data_used,
            unlimited_user_count=billing["unlimited_user_count"],
            volumed_user_count=billing["volumed_user_count"],
            total_user_months=billing["total_user_months"],
        ))
    return result


# ---------------------------------------------------------------------------
# Sub-admin endpoint
# ---------------------------------------------------------------------------
# NOTE: must be registered BEFORE the `/{admin_id}` route below — otherwise
# a GET to /billing/me would be matched as admin_id="me" and 422.

@router.get("/me", response_model=BillingMeResponse)
def get_my_billing(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Return the current admin's own billing info and recent records."""
    billing = _calc_billing_for_admin(current_admin, db)

    records = (
        db.query(BillingRecord)
        .filter(BillingRecord.admin_id == current_admin.id)
        .order_by(BillingRecord.created_at.desc())
        .limit(50)
        .all()
    )

    monthly_traffic_cost = billing["volumed_charge"]
    monthly_user_cost = billing["unlimited_charge"]

    return BillingMeResponse(
        debt=current_admin.debt,
        price_per_user=current_admin.price_per_user,
        price_per_gb=current_admin.price_per_gb,
        unlimited_user_count=billing["unlimited_user_count"],
        volumed_user_count=billing["volumed_user_count"],
        total_user_months=billing["total_user_months"],
        volumed_total_bytes=billing["volumed_total_bytes"],
        estimated_monthly_user_cost=monthly_user_cost,
        estimated_monthly_traffic_cost=monthly_traffic_cost,
        records=[BillingRecordResponse.model_validate(r) for r in records],
    )


# ---------------------------------------------------------------------------
# Admin-scoped endpoints (registered after the literal /me route)
# ---------------------------------------------------------------------------

@router.get("/{admin_id}", response_model=list[BillingRecordResponse])
def get_billing_records(
    admin_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """Return billing records for a specific admin."""
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

    records = (
        db.query(BillingRecord)
        .filter(BillingRecord.admin_id == admin_id)
        .order_by(BillingRecord.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return records


@router.post("/{admin_id}/settle", response_model=BillingRecordResponse)
def settle_debt(
    admin_id: int,
    body: SettleRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """Settle (reduce) a sub-admin's debt.  Amount must be positive and ≤ current debt."""
    if body.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Settlement amount must be positive",
        )

    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

    if body.amount > admin.debt:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Amount exceeds debt of {admin.debt:.2f}",
        )

    admin.debt = round(admin.debt - body.amount, 6)

    record = BillingRecord(
        admin_id=admin_id,
        type=BillingType.SETTLEMENT,
        amount=-round(body.amount, 6),
        description=f"Settled ${body.amount:.2f}",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    emit(
        category=EventCategory.ADMIN_ACTION,
        action="debt_settled",
        username=admin.username,
        admin_username=current_admin.username,
    )

    return record


@router.post("/{admin_id}/topup", response_model=BillingAdminSummary)
def topup_capacity(
    admin_id: int,
    body: TopUpRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """Increase a sub-admin's data_limit (capacity top-up)."""
    if body.bytes <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Top-up amount must be positive",
        )

    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

    if admin.data_limit is not None:
        admin.data_limit += body.bytes
    else:
        admin.data_limit = body.bytes

    db.commit()

    billing = _calc_billing_for_admin(admin, db)

    emit(
        category=EventCategory.ADMIN_ACTION,
        action="capacity_topped_up",
        username=admin.username,
        admin_username=current_admin.username,
    )

    return BillingAdminSummary(
        admin_id=admin.id,
        username=admin.username,
        is_sudo=admin.is_sudo,
        price_per_user=admin.price_per_user,
        price_per_gb=admin.price_per_gb,
        debt=admin.debt,
        data_limit=admin.data_limit,
        data_used=admin.data_used,
        unlimited_user_count=billing["unlimited_user_count"],
        volumed_user_count=billing["volumed_user_count"],
        total_user_months=billing["total_user_months"],
    )


@router.put("/{admin_id}/pricing", response_model=BillingAdminSummary)
def set_pricing(
    admin_id: int,
    body: PricingRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_sudo_admin),
):
    """Set pricing for a sub-admin."""
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

    if body.price_per_user is not None:
        admin.price_per_user = body.price_per_user
    if body.price_per_gb is not None:
        admin.price_per_gb = body.price_per_gb

    db.commit()

    billing = _calc_billing_for_admin(admin, db)

    return BillingAdminSummary(
        admin_id=admin.id,
        username=admin.username,
        is_sudo=admin.is_sudo,
        price_per_user=admin.price_per_user,
        price_per_gb=admin.price_per_gb,
        debt=admin.debt,
        data_limit=admin.data_limit,
        data_used=admin.data_used,
        unlimited_user_count=billing["unlimited_user_count"],
        volumed_user_count=billing["volumed_user_count"],
        total_user_months=billing["total_user_months"],
    )
