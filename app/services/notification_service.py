"""NotificationService — 通知生命周期管理。

支持按 tenant 隔离的 CRUD、标记已读、未读计数。
异常隔离：create() 失败只记录日志，不抛出异常。
"""

from __future__ import annotations

import logging

from datetime import datetime, timezone

from sqlalchemy import func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification

logger = logging.getLogger(__name__)


class NotificationService:
    """通知服务 — 所有方法接受 AsyncSession 和 tenant_id。"""

    @staticmethod
    async def create(
        db: AsyncSession,
        tenant_id: int,
        notification_type: str,
        title: str,
        body: str = "",
    ) -> Notification | None:
        """创建一条通知。失败时只记录日志，返回 None。"""
        try:
            notification = Notification(
                tenant_id=tenant_id,
                notification_type=notification_type,
                title=title,
                body=body,
                read=False,
            )
            db.add(notification)
            await db.flush()
            await db.refresh(notification)
            return notification
        except Exception:
            logger.exception(
                "Failed to create notification for tenant %s: %s",
                tenant_id, title,
            )
            return None

    @staticmethod
    async def list(
        db: AsyncSession,
        tenant_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Notification]:
        """获取通知列表（分页，最新在前）。"""
        query = (
            select(Notification)
            .where(Notification.tenant_id == tenant_id)
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def mark_read(
        db: AsyncSession,
        notification_id: int,
        tenant_id: int,
    ) -> Notification | None:
        """将指定通知标记为已读（含 tenant 隔离校验）。"""
        notification = await db.get(Notification, notification_id)
        if notification is None:
            return None
        if notification.tenant_id != tenant_id:
            return None
        notification.read = True
        notification.read_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(notification)
        return notification

    @staticmethod
    async def mark_all_read(
        db: AsyncSession,
        tenant_id: int,
    ) -> int:
        """将指定租户的所有通知标记为已读。返回更新条数。"""
        now = datetime.now(timezone.utc)
        stmt = (
            update(Notification)
            .where(
                Notification.tenant_id == tenant_id,
                Notification.read == False,  # noqa: E712
            )
            .values(read=True, read_at=now)
        )
        result = await db.execute(stmt)
        await db.flush()
        return result.rowcount

    @staticmethod
    async def get_unread_count(
        db: AsyncSession,
        tenant_id: int,
    ) -> int:
        """统计指定租户的未读通知数量。"""
        query = (
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.tenant_id == tenant_id,
                Notification.read == False,  # noqa: E712
            )
        )
        result = await db.execute(query)
        return result.scalar() or 0

    @staticmethod
    async def delete(
        db: AsyncSession,
        notification_id: int,
        tenant_id: int,
    ) -> bool:
        """删除指定通知（含 tenant 隔离校验）。返回是否删除成功。"""
        notification = await db.get(Notification, notification_id)
        if notification is None:
            return False
        if notification.tenant_id != tenant_id:
            return False
        await db.delete(notification)
        await db.flush()
        return True
