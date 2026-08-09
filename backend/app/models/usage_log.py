"""UsageLog — traffic snapshot for graphing and analytics.

Each row records the bytes sent/received for a user at a given point in
time. This table will grow fast; a retention/cleanup job will be needed
to prune entries older than 30 days by default (configurable via the
USAGE_LOG_RETENTION_DAYS env var). The cleanup job will be implemented
in a later stage.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timestamp: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    bytes_sent: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    bytes_received: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    __table_args__ = (
        Index("ix_usage_logs_user_id_timestamp", "user_id", "timestamp"),
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="usage_logs", lazy="select")
