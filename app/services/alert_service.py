"""AlertService — 告警生命周期管理。

支持按 tenant 隔离的创建、查询、解析、自动过期和触发器注入。

触发器方法（from_*）自带 1h 去重和 circuit breaker（连续 3 次失败后静默降级）。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class _CircuitBreaker:
    """Tracks consecutive failures per key; opens after threshold."""

    def __init__(self, threshold: int = 3) -> None:
        self._threshold = threshold
        self._failures: dict[str, int] = {}

    def record_failure(self, key: str) -> None:
        self._failures[key] = self._failures.get(key, 0) + 1

    def record_success(self, key: str) -> None:
        self._failures.pop(key, None)

    def is_open(self, key: str) -> bool:
        return self._failures.get(key, 0) >= self._threshold


_alert_cb = _CircuitBreaker()


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

        # 异步创建通知 — 失败不影响告警创建，异常内部已隔离
        await NotificationService.create(
            db,
            tenant_id=tenant_id,
            notification_type="alert",
            title=f"Alert: {message}",
            body=f"[{severity}] {message}",
        )

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

    # ── Dedup helper ──────────────────────────────────────────────────────────

    @staticmethod
    async def _has_recent_active_alert(
        db: AsyncSession,
        tenant_id: int,
        source: str,
        alert_type: str,
        window_hours: int = 1,
    ) -> bool:
        """Check if a pending alert with the same source + type exists within the window."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        query = select(Alert).where(
            Alert.tenant_id == tenant_id,
            Alert.source == source,
            Alert.alert_type == alert_type,
            Alert.status == "pending",
            Alert.created_at >= cutoff,
        )
        result = await db.execute(query)
        return result.scalar() is not None

    # ── Trigger methods (fire-and-forget, fail-open) ──────────────────────────

    @staticmethod
    async def from_agent_error(
        db: AsyncSession,
        tenant_id: int,
        source: str,
        error_count: int,
        message: str | None = None,
        metadata: dict | None = None,
    ) -> Alert | None:
        """Create a **critical** alert for an agent with repeated errors.

        Auto-dedup: same source + ``agent_error`` within 1h → return None.
        Circuit breaker: 3 consecutive failures → silent degrade.
        """
        cb_key = f"from_agent_error:{source}"
        if _alert_cb.is_open(cb_key):
            logger.debug("Circuit breaker open for from_agent_error:%s", source)
            return None

        try:
            if await AlertService._has_recent_active_alert(
                db, tenant_id, source, "agent_error",
            ):
                return None

            alert = await AlertService.create_alert(
                db,
                tenant_id=tenant_id,
                alert_type="agent_error",
                severity="critical",
                message=message or f"Agent error count: {error_count}",
                source=source,
                metadata_json=metadata,
            )
            _alert_cb.record_success(cb_key)
            return alert
        except Exception:
            _alert_cb.record_failure(cb_key)
            logger.exception("from_agent_error failed for source=%s", source)
            return None

    @staticmethod
    async def from_quota_warning(
        db: AsyncSession,
        tenant_id: int,
        source: str,
        usage_pct: float,
        message: str | None = None,
        metadata: dict | None = None,
    ) -> Alert | None:
        """Create a **warning** alert for quota approaching the limit.

        Auto-dedup: same source + ``quota_warning`` within 1h → return None.
        """
        cb_key = f"from_quota_warning:{source}"
        if _alert_cb.is_open(cb_key):
            return None

        try:
            if await AlertService._has_recent_active_alert(
                db, tenant_id, source, "quota_warning",
            ):
                return None

            alert = await AlertService.create_alert(
                db,
                tenant_id=tenant_id,
                alert_type="quota_warning",
                severity="warning",
                message=message or f"Quota usage at {usage_pct:.1f}%",
                source=source,
                metadata_json=metadata,
            )
            _alert_cb.record_success(cb_key)
            return alert
        except Exception:
            _alert_cb.record_failure(cb_key)
            logger.exception("from_quota_warning failed for source=%s", source)
            return None

    @staticmethod
    async def from_task_failure(
        db: AsyncSession,
        tenant_id: int,
        source: str,
        fail_count: int,
        message: str | None = None,
        metadata: dict | None = None,
    ) -> Alert | None:
        """Create a **warning** alert for batch task failures.

        Auto-dedup: same source + ``task_failure`` within 1h → return None.
        """
        cb_key = f"from_task_failure:{source}"
        if _alert_cb.is_open(cb_key):
            return None

        try:
            if await AlertService._has_recent_active_alert(
                db, tenant_id, source, "task_failure",
            ):
                return None

            alert = await AlertService.create_alert(
                db,
                tenant_id=tenant_id,
                alert_type="task_failure",
                severity="warning",
                message=message or f"Task failures: {fail_count}",
                source=source,
                metadata_json=metadata,
            )
            _alert_cb.record_success(cb_key)
            return alert
        except Exception:
            _alert_cb.record_failure(cb_key)
            logger.exception("from_task_failure failed for source=%s", source)
            return None

    @staticmethod
    async def from_cost_anomaly(
        db: AsyncSession,
        tenant_id: int,
        source: str,
        increase_pct: float,
        message: str | None = None,
        metadata: dict | None = None,
    ) -> Alert | None:
        """Create an **info** alert for cost spikes compared to yesterday.

        Auto-dedup: same source + ``cost_anomaly`` within 1h → return None.
        """
        cb_key = f"from_cost_anomaly:{source}"
        if _alert_cb.is_open(cb_key):
            return None

        try:
            if await AlertService._has_recent_active_alert(
                db, tenant_id, source, "cost_anomaly",
            ):
                return None

            alert = await AlertService.create_alert(
                db,
                tenant_id=tenant_id,
                alert_type="cost_anomaly",
                severity="info",
                message=message or f"Cost increase: {increase_pct:.1f}% vs yesterday",
                source=source,
                metadata_json=metadata,
            )
            _alert_cb.record_success(cb_key)
            return alert
        except Exception:
            _alert_cb.record_failure(cb_key)
            logger.exception("from_cost_anomaly failed for source=%s", source)
            return None

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
