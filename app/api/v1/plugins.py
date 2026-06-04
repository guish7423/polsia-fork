"""Plugin API — register, list, get, patch, and delete webhook plugins."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.tenant_context import get_current_tenant
from app.services.plugin_registry import (
    call_hooks,
    get_plugin,
    list_plugins,
    register_plugin,
    set_plugin_enabled,
    unregister_plugin,
    update_plugin_config,
)

router = APIRouter(prefix="/plugins", tags=["plugins"])


# ─── Tenant ID dependency ────────────────────────────────────────────────


async def _get_tenant_id() -> int:
    """Extract tenant ID from the current request context."""
    tenant = get_current_tenant()
    if tenant is None:
        raise HTTPException(status_code=401, detail="Tenant context not found — provide a valid X-API-Key header")
    return tenant.id


# ─── Request / Response schemas ────────────────────────────────────────────


class RegisterPluginRequest(BaseModel):
    name: str
    description: str = ""
    webhook_url: str
    manifest: dict = {"version": "1.0", "hooks": []}
    config: dict | None = None


class UpdatePluginRequest(BaseModel):
    enabled: bool | None = None
    config: dict | None = None
    description: str | None = None


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.post("")
async def api_register_plugin(
    body: RegisterPluginRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(_get_tenant_id),
):
    """Register a new plugin."""
    plugin = await register_plugin(
        db,
        tenant_id=tenant_id,
        name=body.name,
        description=body.description,
        webhook_url=body.webhook_url,
        manifest=body.manifest,
        config=body.config,
    )
    return _plugin_response(plugin)


@router.get("")
async def api_list_plugins(
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(_get_tenant_id),
):
    """List all plugins for the current tenant."""
    plugins = await list_plugins(db, tenant_id)
    return [_plugin_response(p) for p in plugins]


@router.get("/{plugin_id}")
async def api_get_plugin(
    plugin_id: int,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(_get_tenant_id),
):
    """Get details for a specific plugin."""
    plugin = await get_plugin(db, plugin_id, tenant_id)
    if not plugin:
        raise HTTPException(404, "Plugin not found")
    return _plugin_response(plugin)


@router.patch("/{plugin_id}")
async def api_patch_plugin(
    plugin_id: int,
    body: UpdatePluginRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(_get_tenant_id),
):
    """Enable/disable or update config/description for a plugin."""
    if body.enabled is not None:
        plugin = await set_plugin_enabled(db, plugin_id, body.enabled, tenant_id)
        if not plugin:
            raise HTTPException(404, "Plugin not found")
    elif body.config is not None or body.description is not None:
        plugin = await update_plugin_config(
            db, plugin_id, tenant_id,
            config=body.config,
            description=body.description,
        )
        if not plugin:
            raise HTTPException(404, "Plugin not found")
    else:
        plugin = await get_plugin(db, plugin_id, tenant_id)
        if not plugin:
            raise HTTPException(404, "Plugin not found")

    return _plugin_response(plugin)


@router.delete("/{plugin_id}")
async def api_delete_plugin(
    plugin_id: int,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(_get_tenant_id),
):
    """Unregister a plugin."""
    removed = await unregister_plugin(db, plugin_id, tenant_id)
    if not removed:
        raise HTTPException(404, "Plugin not found")
    return {"status": "deleted"}


# ─── Internal helpers ──────────────────────────────────────────────────────


def _plugin_response(plugin) -> dict:
    """Serialize a Plugin ORM object to a response dict."""
    return {
        "id": plugin.id,
        "tenant_id": plugin.tenant_id,
        "name": plugin.name,
        "description": plugin.description,
        "version": plugin.version,
        "webhook_url": plugin.webhook_url,
        "manifest": plugin.manifest,
        "enabled": plugin.enabled,
        "config": plugin.config,
        "last_called_at": plugin.last_called_at.isoformat() if plugin.last_called_at else None,
        "last_error": plugin.last_error,
        "created_at": plugin.created_at.isoformat() if plugin.created_at else None,
    }
