"""Alert API — 告警系统的 REST 接口。

遵循现有模式：auth via X-API-Key, tenant 上下文自动注入。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_api_key
from app.core.database import get_db
from app.core.tenant_context import get_current_tenant
from app.services.alert_service import AlertService

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _get_tenant_id(current_tenant) -> int:
    """Extract tenant ID from the current tenant context."""
    if current_tenant is None:
        raise HTTPException(status_code=401, detail="Tenant context required")
    return current_tenant.id


@router.get("/active")
async def get_active_alerts(
    limit: int = Query(50, description="Max results"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_tenant=Depends(get_current_tenant),
):
    """获取当前租户的所有活跃（pending）告警。"""
    tenant_id = _get_tenant_id(current_tenant)
    alerts = await AlertService.get_active_alerts(db, tenant_id=tenant_id, limit=limit)
    return {
        "alerts": [_alert_to_dict(a) for a in alerts],
        "total": len(alerts),
    }


@router.get("/history")
async def get_alert_history(
    limit: int = Query(50, description="Max results"),
    offset: int = Query(0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_tenant=Depends(get_current_tenant),
):
    """获取当前租户的告警历史（含已解决）。"""
    tenant_id = _get_tenant_id(current_tenant)
    alerts = await AlertService.get_alert_history(
        db, tenant_id=tenant_id, limit=limit, offset=offset,
    )
    return {
        "alerts": [_alert_to_dict(a) for a in alerts],
        "total": len(alerts),
    }


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_tenant=Depends(get_current_tenant),
):
    """将指定告警标记为已解决。"""
    tenant_id = _get_tenant_id(current_tenant)
    alert = await AlertService.resolve_alert(db, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    # Tenant isolation — only allow resolving your own alerts
    if alert.tenant_id != tenant_id and tenant_id != 0:
        raise HTTPException(status_code=403, detail="Tenant mismatch")
    return _alert_to_dict(alert)


def _alert_to_dict(alert) -> dict:
    """Serialize Alert ORM object to a plain dict for JSON response."""
    return {
        "id": alert.id,
        "tenant_id": alert.tenant_id,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "message": alert.message,
        "source": alert.source,
        "status": alert.status,
        "metadata_json": alert.metadata_json,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
    }
