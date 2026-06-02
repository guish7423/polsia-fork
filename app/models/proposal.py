"""Proposal model — AI-generated sales proposals for external orders."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), server_default="draft")
    view_token: Mapped[str | None] = mapped_column(
        String(32), unique=True, index=True, nullable=True
    )
    # draft → sent → replied → negotiating → won/lost
    proposed_amount: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), server_default="USD")
    content: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(String(500))
    proposal_metadata: Mapped[dict | None] = mapped_column(JSON)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    won_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
