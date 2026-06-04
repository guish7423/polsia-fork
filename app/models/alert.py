"""Alert model — 系统告警记录。

支持多种告警类型和严重度，按 tenant 隔离。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Alert(Base, TimestampMixin):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"), nullable=False, index=True
    )
    alert_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="告警类型: agent_error / quota_exceeded / cost_anomaly / system"
    )
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="严重度: critical / high / medium / low"
    )
    message: Mapped[str] = mapped_column(Text, nullable=False, comment="告警消息")
    source: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="告警来源: agent / quota / system"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending",
        comment="状态: pending / resolved"
    )
    metadata_json: Mapped[dict | None] = mapped_column(
        JSON, comment="附加元数据（JSON）"
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="解决时间"
    )
