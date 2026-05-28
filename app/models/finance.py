"""Finance models."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RevenueSnapshot(Base):
    __tablename__ = "revenue_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    mrr_cents: Mapped[int] = mapped_column(Integer, server_default="0")
    arr_cents: Mapped[int] = mapped_column(Integer, server_default="0")
    active_subscribers: Mapped[int] = mapped_column(Integer, server_default="0")
    churned_today: Mapped[int] = mapped_column(Integer, server_default="0")
    new_today: Mapped[int] = mapped_column(Integer, server_default="0")
    total_revenue_month_cents: Mapped[int] = mapped_column(
        Integer, server_default="0"
    )
    stripe_balance_cents: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ExpenseRecord(Base):
    __tablename__ = "expense_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    vendor: Mapped[str] = mapped_column(String(255), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), server_default="usd")
    description: Mapped[str | None] = mapped_column(Text)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    external_ref: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
