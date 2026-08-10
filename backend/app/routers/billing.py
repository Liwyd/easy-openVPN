"""Billing router — debt tracking, settlements, top-ups, and pricing.

GET  /api/billing/summary          — sudo: all admins' billing overview
GET  /api/billing/me               — any admin: own debt view
GET  /api/billing/{admin_id}       — sudo: one admin's records
POST /api/billing/{admin_id}/settle — sudo: settle debt
POST /api/billing/{admin_id}/topup  — sudo: increase capacity
PUT  /api/billing/{admin_id}/pricing — sudo: set prices
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.bot.events import EventCategory, emit
from app.db import get_db
from app.models.admin import Admin
from app.models.billing import BillingRecord, BillingType
from app.schemas.billing import (
    BillingAdminSummary,
    BillingMeResponse,
    BillingRecordResponse,
    PricingRequest,
    SettleRequest,
    TopUpRequest,
)
from app.services.auth import get_current_admin, get_current_sudo_admin
from app.services.billing import calc_charges_for_admin, calculate_admin_debt

router = APIRouter(prefix="/api/billing", tags=["billing"])


def _billing_summary(admin: Admin, db: Session) -> BillingAdminSummary:
    """Build a BillingAdminSummary with a live-computed debt."""
    billing = calc_charges_for_admin(admin, db)
    return BillingAdminSummary(
        admin_id=admin.id,
        username=admin.username,
        is_sudo=admin.is_sudo,
        price_per_user=admin.price_per_user,
        price_per_gb=admin.price_per_gb,
        debt=calculate_admin_debt(admin, db),
        data_limit=admin.data_limit,
        data_used=admin.data_used,
        unlimited_user_count=billing["unlimited_user_count"],
        volumed_user_count=billing["volumed_user_count"],
        total_user_months=billing["total_user_months"],
    )


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
        result.append(_billing_summary(adm, db))
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
    billing = calc_charges_for_admin(current_admin, db)
    debt = calculate_admin_debt(current_admin, db)

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
        debt=debt,
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

    current_debt = calculate_admin_debt(admin, db)
    if body.amount > current_debt:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Amount exceeds debt of {current_debt:.2f}",
        )

    admin.debt = round(current_debt - body.amount, 6)

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

    emit(
        category=EventCategory.ADMIN_ACTION,
        action="capacity_topped_up",
        username=admin.username,
        admin_username=current_admin.username,
    )

    return _billing_summary(admin, db)


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

    return _billing_summary(admin, db)
