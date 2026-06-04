"""Notifications API — 通知系统的 REST 接口。

遵循现有模式：auth via X-API-Key, tenant 上下文自动注入。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_api_key
from app.core.database import get_db
from app.core.tenant_context import get_current_tenant
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _get_tenant_id(current_tenant) -> int:
    """Extract tenant ID from the current tenant context."""
    if current_tenant is None:
        raise HTTPException(status_code=401, detail="Tenant context required")
    return current_tenant.id


def _notification_to_dict(n) -> dict:
    """Serialize Notification ORM object to a plain dict for JSON response."""
    return {
        "id": n.id,
        "tenant_id": n.tenant_id,
        "notification_type": n.notification_type,
        "title": n.title,
        "body": n.body,
        "read": n.read,
        "created_at": n.created_at.isoformat() if n.created_at else None,
        "read_at": n.read_at.isoformat() if n.read_at else None,
    }


@router.get("")
async def list_notifications(
    limit: int = Query(50, description="Max results"),
    offset: int = Query(0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_tenant=Depends(get_current_tenant),
):
    """获取当前租户的通知列表（分页，最新在前）。"""
    tenant_id = _get_tenant_id(current_tenant)
    notifications = await NotificationService.list(
        db, tenant_id=tenant_id, limit=limit, offset=offset,
    )
    return {
        "notifications": [_notification_to_dict(n) for n in notifications],
        "total": len(notifications),
    }


@router.get("/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_tenant=Depends(get_current_tenant),
):
    """获取当前租户的未读通知数量。"""
    tenant_id = _get_tenant_id(current_tenant)
    count = await NotificationService.get_unread_count(db, tenant_id=tenant_id)
    return {"unread_count": count}


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_tenant=Depends(get_current_tenant),
):
    """将指定通知标记为已读。"""
    tenant_id = _get_tenant_id(current_tenant)
    notification = await NotificationService.mark_read(
        db, notification_id, tenant_id=tenant_id,
    )
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return _notification_to_dict(notification)


@router.post("/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_tenant=Depends(get_current_tenant),
):
    """将当前租户的所有通知标记为已读。"""
    tenant_id = _get_tenant_id(current_tenant)
    marked = await NotificationService.mark_all_read(db, tenant_id=tenant_id)
    return {"marked": marked}
