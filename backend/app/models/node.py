"""Node model — future feature: attach nodes to users so each user can
reach only the nodes selected for them via their subscription link.

This is a placeholder for a planned update: node registration, health
checks and per-user node routing are NOT implemented yet. Only the DB
schema (nodes table + user_nodes association) is in place so the feature
can be built without further migrations.
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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# Many-to-many association between users and nodes.
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

    Only the schema is implemented for now — the node registration UI,
    health checks and subscription routing will come in a later update.
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

    users: Mapped[list[User]] = relationship(
        "User", secondary=user_nodes, back_populates="nodes", lazy="select"
    )
