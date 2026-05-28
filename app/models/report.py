"""Daily report model."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class DailyReport(Base, TimestampMixin):
    __tablename__ = "daily_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    morning_plan: Mapped[str | None] = mapped_column(Text)
    evening_summary: Mapped[str | None] = mapped_column(Text)
    tasks_planned: Mapped[int] = mapped_column(Integer, server_default="0")
    tasks_completed: Mapped[int] = mapped_column(Integer, server_default="0")
    tasks_failed: Mapped[int] = mapped_column(Integer, server_default="0")
    metrics_snapshot: Mapped[dict | None] = mapped_column(JSON)
    insights: Mapped[list | None] = mapped_column(JSON)
