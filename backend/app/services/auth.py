"""Auth dependencies — FastAPI ``Depends()`` functions for JWT authentication.

These are standalone async functions (not classmethods) so they work
cleanly with FastAPI's dependency injection.  The Admin model stays
pure ORM — no web-framework imports.
"""

from __future__ import annotations

import datetime as dt

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.admin import Admin
from app.services.jwt import decode_token

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/token")


async def get_current_admin(
    token: str = Depends(_oauth2_scheme),
    db: Session = Depends(get_db),
) -> Admin:
    """Return the current admin from a valid JWT, or raise 401."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(db, token)
    if payload is None:
        raise credentials_exc
    username: str | None = payload.get("sub")
    if username is None:
        raise credentials_exc
    admin = db.query(Admin).filter(Admin.username == username).first()
    if admin is None:
        raise credentials_exc
    if admin.disabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is disabled",
        )
    # Password-reset invalidation: reject tokens created before password_reset_at.
    created_at_raw = payload.get("created_at")
    if admin.password_reset_at is not None and created_at_raw is not None:
        try:
            token_created_at = dt.datetime.fromisoformat(created_at_raw)
            password_reset = admin.password_reset_at
            if password_reset.tzinfo is None:
                password_reset = password_reset.replace(tzinfo=dt.UTC)
            if token_created_at < password_reset:
                raise credentials_exc
        except (ValueError, TypeError):
            raise credentials_exc from None
    return admin


async def get_current_sudo_admin(
    current_admin: Admin = Depends(get_current_admin),
) -> Admin:
    """Like get_current_admin, but additionally requires sudo privileges."""
    if not current_admin.is_sudo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sudo admin privileges required",
        )
    return current_admin
