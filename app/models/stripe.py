"""Stripe event model."""

from datetime import datetime

from sqlalchemy import func, DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StripeEvent(Base):
    __tablename__ = "stripe_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stripe_event_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String(255))
    amount_cents: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(50), server_default="processed")
    raw_payload: Mapped[dict | None] = mapped_column(JSON)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
