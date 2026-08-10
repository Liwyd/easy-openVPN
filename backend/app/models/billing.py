"""BillingRecord model — ledger of charges and settlements.

Each row is an immutable ledger entry. Charges increase debt;
settlements decrease it.  The admin.debt field is a denormalized
running total kept in sync by the billing cron and settlement endpoint.
"""

from __future__ import annotations

import datetime as dt
import enum

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class BillingType(str, enum.Enum):
    USER_CHARGE = "user_charge"
    TRAFFIC_CHARGE = "traffic_charge"
    SETTLEMENT = "settlement"


class BillingRecord(Base):
    __tablename__ = "billing_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("admins.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[BillingType] = mapped_column(
        Enum(BillingType, native_enum=False), nullable=False
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
