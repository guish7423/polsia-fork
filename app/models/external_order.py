"""ExternalOrder model — orders from Upwork, Fiverr, 猪八戒, etc."""

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ExternalOrder(Base):
    __tablename__ = "external_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), default="internal")
    external_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), server_default="scanned")
    budget_min: Mapped[float | None] = mapped_column(Float)
    budget_max: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), server_default="USD")
    description: Mapped[str | None] = mapped_column(Text)
    requirements: Mapped[str | None] = mapped_column(Text)
    provider_notes: Mapped[str | None] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(Float)
    score_reason: Mapped[str | None] = mapped_column(Text)
    assigned_agent: Mapped[str | None] = mapped_column(String(100))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    deliverables: Mapped[list | None] = mapped_column(JSON)
    delivery_notes: Mapped[str | None] = mapped_column(Text)
    execution_status: Mapped[str | None] = mapped_column(String(50), server_default="pending")
    deploy_dir: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
