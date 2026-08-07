"""JWT secret — single-row table storing the HMAC signing key.

The secret is auto-generated on first startup.  To rotate, update the
DB row and restart the process.
"""

from __future__ import annotations

import secrets

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base


class JWTSecret(Base):
    __tablename__ = "jwt"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    secret_key: Mapped[str] = mapped_column(String(256), nullable=False)


def get_jwt_secret(db: Session) -> str:
    """Return the JWT signing secret, creating one if the table is empty.

    The secret is NOT cached across requests — each call reads from the
    DB so that test isolation works and secret rotation takes effect
    immediately after a restart (the row is updated, then the process
    restarts).
    """
    row = db.query(JWTSecret).first()
    if row is None:
        row = JWTSecret(secret_key=secrets.token_hex(32))
        db.add(row)
        db.flush()
    return row.secret_key
