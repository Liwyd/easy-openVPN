"""Node model — VPN nodes with admin-level access control.

Each node represents a VPN server endpoint. Admins are granted access to
specific nodes via the ``admin_nodes`` association table. When a new node
is created it is auto-assigned to **all** existing admins; a sudo admin
can later revoke (uncheck) access for individual sub-admins.

The ``user_nodes`` M2M table links users to the specific nodes their
subscription grants access to.  Node health checks, registration and
per-user routing are NOT implemented yet — this module provides the DB
schema and association logic only.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# ── Association tables ───────────────────────────────────────────────────

# Many-to-many: admin <-> node (which admins can see/manage which nodes).
admin_nodes = Table(
    "admin_nodes",
    Base.metadata,
    Column(
        "admin_id",
        Integer,
        ForeignKey("admins.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "node_id",
        Integer,
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
)

# Many-to-many: user <-> node (which nodes a user's subscription reaches).
user_nodes = Table(
    "user_nodes",
    Base.metadata,
    Column(
        "user_id",
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "node_id",
        Integer,
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Node(Base):
    """A VPN node a user may access through their subscription.

    Only the schema and admin-association logic are implemented for now —
    the node registration UI, health checks and subscription routing will
    come in a later update.
    """

    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=1194)
    protocol: Mapped[str] = mapped_column(String(16), nullable=False, default="udp")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Management fields (future feature support) ──────────────────────
    usage_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="online"
    )  # online | offline | error
    last_health_check: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    country_code: Mapped[str | None] = mapped_column(
        String(2), nullable=True, default=None
    )
    city: Mapped[str | None] = mapped_column(
        String(64), nullable=True, default=None
    )
    max_users: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None
    )
    current_users: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    tags: Mapped[list | None] = mapped_column(
        Text, nullable=True, default=None
    )  # JSON list of string tags
    note: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        onupdate=func.now(),
    )

    # ── Relationships ───────────────────────────────────────────────────
    users: Mapped[list[User]] = relationship(
        "User", secondary=user_nodes, back_populates="nodes", lazy="select"
    )
    admins: Mapped[list[Admin]] = relationship(
        "Admin", secondary=admin_nodes, back_populates="nodes", lazy="select"
    )
