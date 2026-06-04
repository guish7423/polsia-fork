"""Tenant model — multi-tenant organization."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )

    # Plan & limits — Tenant is the authority
    plan: Mapped[str] = mapped_column(String(50), default="starter")
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    agents_limit: Mapped[int] = mapped_column(Integer, default=3)
    tasks_monthly_limit: Mapped[int] = mapped_column(Integer, default=1000)
    tokens_monthly_limit: Mapped[int] = mapped_column(Integer, default=10_000_000)
    cost_monthly_limit_usd: Mapped[float] = mapped_column(Float, default=50.0)
    rpm_limit: Mapped[int] = mapped_column(Integer, default=60)

    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    @classmethod
    def get_plan_defaults(cls, plan: str) -> dict:
        """Return limit defaults per plan tier."""
        return {
            "starter": {
                "agents_limit": 3,
                "tasks_monthly_limit": 1000,
                "tokens_monthly_limit": 10_000_000,
                "cost_monthly_limit_usd": 50.0,
                "rpm_limit": 60,
            },
            "pro": {
                "agents_limit": 10,
                "tasks_monthly_limit": 10_000,
                "tokens_monthly_limit": 50_000_000,
                "cost_monthly_limit_usd": 200.0,
                "rpm_limit": 300,
            },
            "enterprise": {
                "agents_limit": 50,
                "tasks_monthly_limit": 100_000,
                "tokens_monthly_limit": 500_000_000,
                "cost_monthly_limit_usd": 1000.0,
                "rpm_limit": 1000,
            },
        }.get(plan, {})
