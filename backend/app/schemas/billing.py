"""Billing schemas — request/response models for billing endpoints."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class BillingRecordResponse(BaseModel):
    id: int
    admin_id: int
    type: str
    amount: float
    description: str
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class BillingAdminSummary(BaseModel):
    admin_id: int
    username: str
    is_sudo: bool
    price_per_user: float | None
    price_per_gb: float | None
    debt: float
    data_limit: int | None
    data_used: int
    unlimited_user_count: int
    volumed_user_count: int
    total_user_months: int

    model_config = {"from_attributes": True}


class SettleRequest(BaseModel):
    amount: float


class TopUpRequest(BaseModel):
    bytes: int


class PricingRequest(BaseModel):
    price_per_user: float | None = None
    price_per_gb: float | None = None


class BillingMeResponse(BaseModel):
    debt: float
    price_per_user: float | None
    price_per_gb: float | None
    unlimited_user_count: int
    volumed_user_count: int
    total_user_months: int
    volumed_total_bytes: int
    estimated_monthly_user_cost: float
    estimated_monthly_traffic_cost: float
    records: list[BillingRecordResponse]
