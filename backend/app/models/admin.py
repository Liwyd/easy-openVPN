"""Admin model — hierarchical administrator with quota management.

Unlike Marzban's flat admin model, eovpanel admins have a configurable
data_limit that caps the TOTAL traffic of all users and child admins
beneath them. sudo admins have unlimited quota (data_limit=NULL).

The parent_admin_id FK forms the admin hierarchy tree. A non-sudo admin
can only manage their own users within their own remaining quota.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)
    is_sudo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    disabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # JWT invalidation — when password is reset, set this timestamp;
    # during token validation, reject tokens created before this time.
    password_reset_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Hierarchical quota — a cap on the TOTAL traffic (bytes) of all users
    # owned by this admin. NULL = unlimited. For non-sudo admins this is
    # REQUIRED (assigned by the creating sudo admin). For sudo admins
    # this is NULL (unlimited).
    data_limit: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)

    # Denormalized running total of traffic consumed by all users under
    # this admin. Updated by the usage-accounting job (later stage).
    data_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Admin hierarchy — who created this admin. NULL for top-level sudo admin.
    parent_admin_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("admins.id", ondelete="SET NULL"), nullable=True, default=None
    )

    # Billing — pricing and accumulated debt for sub-admins.
    # price_per_user: $ per unlimited user per month (set by sudo).
    # price_per_gb: $ per GB of traffic (set by sudo).
    # debt: accumulated debt (charges go up, settlements go down, never negative).
    price_per_user: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    price_per_gb: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    debt: Mapped[float] = mapped_column(Float, default=0, nullable=False)

    # Relationships
    parent_admin: Mapped[Admin | None] = relationship(
        "Admin", remote_side="Admin.id", back_populates="child_admins", lazy="select"
    )
    child_admins: Mapped[list[Admin]] = relationship(
        "Admin", back_populates="parent_admin", lazy="select"
    )
    users: Mapped[list[User]] = relationship("User", back_populates="admin", lazy="select")
    admin_logs: Mapped[list[AdminLog]] = relationship(
        "AdminLog", back_populates="admin", lazy="select"
    )
