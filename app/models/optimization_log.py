"""Optimization log model — tracks agent self-optimization events."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OptimizationLog(Base):
    __tablename__ = "optimization_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    agent_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(50), nullable=False)
    """One of: success_rate, avg_duration, token_efficiency."""
    before_value: Mapped[float] = mapped_column(Float, nullable=False)
    after_value: Mapped[float] = mapped_column(Float, nullable=False)
    adjustment: Mapped[dict] = mapped_column(JSON, nullable=False)
    """JSON describing what changed / what was recommended."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
