"""AlertService — 告警生命周期管理。

支持按 tenant 隔离的创建、查询、解析和自动过期。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert


class AlertService:
    """告警服务 — 所有方法接受 AsyncSession 和可选的 tenant_id。"""

    @staticmethod
    async def create_alert(
        db: AsyncSession,
        tenant_id: int,
        alert_type: str,
        severity: str,
        message: str,
        source: str,
        metadata_json: dict | None = None,
    ) -> Alert:
        """创建一条新告警。"""
        alert = Alert(
            tenant_id=tenant_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            source=source,
            status="pending",
            metadata_json=metadata_json,
        )
        db.add(alert)
        await db.flush()
        await db.refresh(alert)
        return alert

    @staticmethod
    async def resolve_alert(db: AsyncSession, alert_id: int) -> Alert | None:
        """将告警标记为已解决。"""
        alert = await db.get(Alert, alert_id)
        if alert is None:
            return None
        alert.status = "resolved"
        alert.resolved_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(alert)
        return alert

    @staticmethod
    async def get_active_alerts(
        db: AsyncSession,
        tenant_id: int,
        limit: int = 50,
    ) -> list[Alert]:
        """获取指定租户的所有活跃（pending）告警。

        Args:
            db: 数据库会话
            tenant_id: 租户 ID
            limit: 最大返回数量
        """
        query = (
            select(Alert)
            .where(Alert.tenant_id == tenant_id, Alert.status == "pending")
            .order_by(Alert.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_alert_history(
        db: AsyncSession,
        tenant_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Alert]:
        """获取指定租户的所有告警历史（含已解决）。

        Args:
            db: 数据库会话
            tenant_id: 租户 ID
            limit: 最大返回数量
            offset: 分页偏移
        """
        query = (
            select(Alert)
            .where(Alert.tenant_id == tenant_id)
            .order_by(Alert.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def auto_resolve_old(
        db: AsyncSession,
        days: int = 7,
        tenant_id: int | None = None,
    ) -> int:
        """自动解决超过指定天数的 pending 告警。

        Args:
            db: 数据库会话
            days: 超过此天数的告警将被自动解决
            tenant_id: 可选，指定租户

        Returns:
            被解决的告警数量
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        query = select(Alert).where(
            Alert.status == "pending",
            Alert.created_at < cutoff,
        )
        if tenant_id is not None:
            query = query.where(Alert.tenant_id == tenant_id)

        result = await db.execute(query)
        alerts = list(result.scalars().all())

        now = datetime.now(timezone.utc)
        for alert in alerts:
            alert.status = "resolved"
            alert.resolved_at = now

        await db.flush()
        return len(alerts)

    @staticmethod
    async def count_active(
        db: AsyncSession,
        tenant_id: int,
    ) -> int:
        """统计指定租户的活跃告警数量。"""
        query = select(func.count()).select_from(Alert).where(
            Alert.tenant_id == tenant_id,
            Alert.status == "pending",
        )
        result = await db.execute(query)
        return result.scalar() or 0
