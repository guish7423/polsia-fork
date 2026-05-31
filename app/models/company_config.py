"""Company configuration model."""

from sqlalchemy import Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CompanyConfig(Base, TimestampMixin):
    __tablename__ = "company_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    mission: Mapped[str | None] = mapped_column(Text)
    vision: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    target_market: Mapped[str | None] = mapped_column(Text)
    value_prop: Mapped[str | None] = mapped_column(Text)
    pricing_model: Mapped[dict | None] = mapped_column(JSON)
    goals: Mapped[dict | None] = mapped_column(JSON)
    kpis: Mapped[dict | None] = mapped_column(JSON)
    website_url: Mapped[str | None] = mapped_column(String(512))
    github_repo: Mapped[str | None] = mapped_column(String(512))
    product_type: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(50), server_default="UTC")
    daily_cycle_hour: Mapped[int] = mapped_column(Integer, server_default="6")
