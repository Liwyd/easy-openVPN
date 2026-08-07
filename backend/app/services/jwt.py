"""JWT service — access + refresh token creation and validation.

The signing secret is stored in a single-row ``jwt`` DB table
(see ``app.models.jwt``) and cached via ``lru_cache`` for performance.
Rotating the secret requires updating the DB row and restarting the
process (or clearing the cache).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from jose import JWTError, jwt

from app.config import JWT_ACCESS_TOKEN_EXPIRE_MINUTES, JWT_ALGORITHM, JWT_REFRESH_TOKEN_EXPIRE_DAYS
from app.models.jwt import get_jwt_secret


def create_access_token(db, admin_id: int, username: str, is_sudo: bool) -> str:
    """Create a short-lived access token."""
    secret = get_jwt_secret(db)
    now = dt.datetime.now(dt.UTC)
    expire = now + dt.timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": username,
        "is_sudo": is_sudo,
        "iat": int(now.timestamp()),
        "created_at": now.isoformat(),
        "exp": expire,
        "type": "access",
        "admin_id": admin_id,
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def create_refresh_token(db, admin_id: int, username: str, is_sudo: bool) -> str:
    """Create a long-lived refresh token."""
    secret = get_jwt_secret(db)
    now = dt.datetime.now(dt.UTC)
    expire = now + dt.timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": username,
        "is_sudo": is_sudo,
        "iat": int(now.timestamp()),
        "created_at": now.isoformat(),
        "exp": expire,
        "type": "refresh",
        "admin_id": admin_id,
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_token(db, token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT token.

    Returns the payload dict on success, or None if the token is
    invalid / expired / has the wrong type.
    """
    secret = get_jwt_secret(db)
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
