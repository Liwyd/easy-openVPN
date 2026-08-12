"""User (VPN client) model — represents a single VPN client certificate/user.

Username must be a valid OpenVPN common-name-safe string: alphanumeric,
hyphens, underscores only, max 64 chars.

Each user is owned by an Admin. The subscription_token is a random,
unguessable string used for the public subscription-link feature.
"""

from __future__ import annotations

import datetime as dt
import enum
import secrets

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    EXPIRED = "expired"
    LIMITED = "limited"


class DataLimitResetStrategy(str, enum.Enum):
    NO_RESET = "no_reset"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    admin_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("admins.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, native_enum=False), default=UserStatus.ACTIVE, nullable=False, index=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Data quota — nullable = unlimited. Updated by usage-accounting job.
    data_limit: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    data_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Quota reset strategy — mirrors Marzban's UX pattern.
    data_limit_reset_strategy: Mapped[DataLimitResetStrategy] = mapped_column(
        Enum(DataLimitResetStrategy, native_enum=False),
        default=DataLimitResetStrategy.NO_RESET,
        nullable=False,
    )

    # Hard expiry — after this datetime the user's cert is revoked / connection killed.
    expire_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None, index=True
    )

    # Optional daily allowed-connection window (time-of-day only).
    # e.g. only allow connections 08:00–22:00.
    time_window_start: Mapped[dt.time | None] = mapped_column(Time, nullable=True, default=None)
    time_window_end: Mapped[dt.time | None] = mapped_column(Time, nullable=True, default=None)

    # Free-text note for admin use.
    note: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    # Certificate reference — maps this DB row to the actual easy-rsa
    # generated client cert. revoked=True means the cert has been revoked.
    cert_serial: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    common_name: Mapped[str | None] = mapped_column(String(128), nullable=True, default=None)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Subscription link — random unguessable token for the public
    # /sub/{token} endpoint. Generated on creation via secrets.token_urlsafe(32).
    subscription_token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, default=""
    )
    subscription_updated_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Needed by the periodic quota-reset job — added now to avoid a follow-up migration.
    last_reset_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Per-user byte-counter snapshot used by the usage-sync job.
    # last_rx/last_tx hold the last observed session counters from the
    # OpenVPN management interface; last_connected_since disambiguates
    # reconnects whose new session already outgrew the old baseline.
    # Persisted in the DB (not process memory) so a disconnect or backend
    # restart cannot lose the baseline — otherwise a reconnect would
    # re-seed it and silently undercount the whole new session.
    last_rx: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    last_tx: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    last_connected_since: Mapped[str | None] = mapped_column(
        String(64), nullable=True, default=None
    )

    # Relationships
    admin: Mapped[Admin] = relationship("Admin", back_populates="users", lazy="select")
    usage_logs: Mapped[list[UsageLog]] = relationship(
        "UsageLog", back_populates="user", lazy="select", cascade="all, delete-orphan"
    )
    nodes: Mapped[list[Node]] = relationship(
        "Node", secondary="user_nodes", back_populates="users", lazy="select"
    )

    def __init__(self, **kwargs):
        # Auto-generate subscription_token if not provided.
        if "subscription_token" not in kwargs or not kwargs["subscription_token"]:
            kwargs["subscription_token"] = secrets.token_urlsafe(32)
        super().__init__(**kwargs)
