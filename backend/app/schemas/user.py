"""User schemas — request/response models for user CRUD endpoints."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, field_validator

from app.models.user import DataLimitResetStrategy, UserStatus
from app.utils.validation import validate_username


class UserCreate(BaseModel):
    username: str
    data_limit: int | None = None  # None = unlimited (if admin is sudo)
    expire_at: dt.datetime | None = None
    time_window_start: dt.time | None = None
    time_window_end: dt.time | None = None
    note: str | None = None
    status: UserStatus = UserStatus.ACTIVE

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str) -> str:
        validate_username(v)
        return v


class UserUpdate(BaseModel):
    data_limit: int | None = None
    expire_at: dt.datetime | None = None
    time_window_start: dt.time | None = None
    time_window_end: dt.time | None = None
    note: str | None = None
    status: UserStatus | None = None


class UserResponse(BaseModel):
    """Admin-facing user response — does NOT expose subscription_token."""

    id: int
    username: str
    admin_id: int
    status: UserStatus
    created_at: dt.datetime
    data_limit: int | None
    data_used: int
    data_limit_reset_strategy: DataLimitResetStrategy
    expire_at: dt.datetime | None
    time_window_start: dt.time | None = None
    time_window_end: dt.time | None = None
    note: str | None
    revoked: bool
    common_name: str | None = None

    model_config = {"from_attributes": True}


class SubscriptionURLResponse(BaseModel):
    subscription_url: str
