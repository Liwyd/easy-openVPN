"""Auth router — login (OAuth2 password flow) + refresh token + change password."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.admin import Admin
from app.schemas.auth import AdminProfile, RefreshRequest, TokenRequest, TokenResponse
from app.services.auth import get_current_admin
from app.services.jwt import create_access_token, create_refresh_token, decode_token
from app.utils.password import hash_password, verify_password

router = APIRouter(prefix="/api/admin", tags=["auth"])


@router.post("/token", response_model=TokenResponse)
def login(body: TokenRequest, db: Session = Depends(get_db)):
    """Authenticate an admin and return access + refresh tokens."""
    admin = db.query(Admin).filter(Admin.username == body.username).first()
    if admin is None or not verify_password(body.password, admin.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if admin.disabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is disabled",
        )
    access = create_access_token(db, admin.id, admin.username, admin.is_sudo)
    refresh = create_refresh_token(db, admin.id, admin.username, admin.is_sudo)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for new access + refresh tokens."""
    payload = decode_token(db, body.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    username = payload.get("sub")
    admin = db.query(Admin).filter(Admin.username == username).first()
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin not found",
        )
    if admin.disabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is disabled",
        )
    # Password-reset invalidation
    import datetime as _dt

    created_at_raw = payload.get("created_at")
    if admin.password_reset_at is not None and created_at_raw is not None:
        try:
            token_created = _dt.datetime.fromisoformat(created_at_raw)
            pw_reset = admin.password_reset_at
            if pw_reset.tzinfo is None:
                pw_reset = pw_reset.replace(tzinfo=_dt.UTC)
            if token_created < pw_reset:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token invalidated by password reset",
                )
        except (ValueError, TypeError):
            pass
    access = create_access_token(db, admin.id, admin.username, admin.is_sudo)
    refresh_token = create_refresh_token(db, admin.id, admin.username, admin.is_sudo)
    return TokenResponse(access_token=access, refresh_token=refresh_token)


@router.get("/me", response_model=AdminProfile)
def get_me(
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Return the logged-in admin's profile including quota info."""
    return AdminProfile(
        id=current_admin.id,
        username=current_admin.username,
        is_sudo=current_admin.is_sudo,
        disabled=current_admin.disabled,
        created_at=current_admin.created_at,
        data_limit=current_admin.data_limit,
        data_used=current_admin.data_used,
        parent_admin_id=current_admin.parent_admin_id,
    )


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.put("/me/password")
def change_my_password(
    body: ChangePasswordRequest,
    current_admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Allow any authenticated admin to change their own password."""
    if not verify_password(body.current_password, current_admin.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    current_admin.hashed_password = hash_password(body.new_password)
    current_admin.password_reset_at = dt.datetime.now(dt.UTC)
    db.commit()

    return {"detail": "Password updated successfully"}
