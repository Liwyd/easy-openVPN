"""AdminLog — audit trail for every admin action.

Every create/update/delete/enable/disable of a user or admin must be
recorded here. The actual logging calls will be wired in a later stage
when endpoints exist; for now we define the table schema.
"""

from __future__ import annotations

import datetime as dt
import enum

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class AdminAction(str, enum.Enum):
    CREATE_USER = "create_user"
    UPDATE_USER = "update_user"
    DELETE_USER = "delete_user"
    DISABLE_USER = "disable_user"
    ENABLE_USER = "enable_user"
    CREATE_ADMIN = "create_admin"
    UPDATE_ADMIN = "update_admin"
    DELETE_ADMIN = "delete_admin"
    RESET_USAGE = "reset_usage"
    REGENERATE_SUBSCRIPTION = "regenerate_subscription"
    UPDATE_SERVER_CONFIG = "update_server_config"


class TargetType(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"
    SERVER_CONFIG = "server_config"


class AdminLog(Base):
    __tablename__ = "admin_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("admins.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[AdminAction] = mapped_column(
        Enum(AdminAction, native_enum=False), nullable=False
    )
    target_type: Mapped[TargetType] = mapped_column(
        Enum(TargetType, native_enum=False), nullable=False
    )
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    timestamp: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    detail: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    __table_args__ = (
        Index("ix_admin_logs_admin_id_timestamp", "admin_id", "timestamp"),
    )

    # Relationships
    admin: Mapped[Admin] = relationship("Admin", back_populates="admin_logs", lazy="select")
