"""Auth schemas — request/response models for login and token endpoints."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class TokenRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class AdminProfile(BaseModel):
    id: int
    username: str
    is_sudo: bool
    disabled: bool
    created_at: dt.datetime
    data_limit: int | None
    data_used: int
    parent_admin_id: int | None

    model_config = {"from_attributes": True}
