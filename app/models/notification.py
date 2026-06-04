"""Notification model — 系统通知记录。

支持多种通知类型，按 tenant 隔离，标记已读/未读。
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"), nullable=False, index=True
    )
    notification_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="通知类型: alert / billing / system / agent",
    )
    title: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="通知标题"
    )
    body: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="通知正文"
    )
    read: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0",
        comment="是否已读",
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="读取时间"
    )
