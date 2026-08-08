"""Admin schemas — request/response models for admin CRUD endpoints."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, field_validator

from app.utils.validation import validate_username


class AdminCreate(BaseModel):
    username: str
    password: str
    data_limit: int  # required for non-sudo admins
    is_sudo: bool = False

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str) -> str:
        validate_username(v)
        return v


class AdminUpdate(BaseModel):
    data_limit: int | None = None
    disabled: bool | None = None
    password: str | None = None


class AdminResponse(BaseModel):
    id: int
    username: str
    is_sudo: bool
    disabled: bool
    created_at: dt.datetime
    data_limit: int | None
    data_used: int
    parent_admin_id: int | None

    model_config = {"from_attributes": True}


class AdminUsageResponse(BaseModel):
    admin_id: int
    username: str
    data_limit: int | None
    data_used: int
    remaining: int | None
    child_admins_bytes: int
    direct_users_bytes: int
