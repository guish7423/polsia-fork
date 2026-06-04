"""Agent generation config model — versioned gen_config per (tenant, agent_type)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AgentGenConfig(Base):
    __tablename__ = "agent_gen_configs"

    __table_args__ = (
        UniqueConstraint("tenant_id", "agent_type", "version", name="uq_tenant_agent_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    agent_type: Mapped[str] = mapped_column(String(100), nullable=False)

    version: Mapped[int] = mapped_column(Integer, nullable=False)
    """Auto-increment per (tenant_id, agent_type)."""

    temperature: Mapped[float | None] = mapped_column(Float)
    max_tokens: Mapped[int | None] = mapped_column(Integer)
    top_p: Mapped[float | None] = mapped_column(Float)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    applied_by: Mapped[str] = mapped_column(String(50), nullable=False)
    """One of: auto_tune, manual, initial."""

    optimization_log_id: Mapped[int | None] = mapped_column(
        ForeignKey("optimization_logs.id"),
        nullable=True,
    )

    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    """Timestamp of last rollback — tracks cooldown."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
