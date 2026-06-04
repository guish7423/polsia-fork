"""Plugin registry — register, list, enable/disable, and invoke webhook-based plugins."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plugin_hooks import validate_hook_name
from app.models.plugin import Plugin

logger = logging.getLogger(__name__)


# ─── CRUD ───────────────────────────────────────────────────────────────────


async def register_plugin(
    db: AsyncSession,
    tenant_id: int,
    name: str,
    description: str = "",
    webhook_url: str = "",
    manifest: dict | None = None,
    config: dict | None = None,
    version: str = "1.0",
) -> Plugin:
    """Register a new plugin for the given *tenant_id*."""
    # 校验 manifest 中声明的 hooks 是否有效
    manifest = manifest or {"version": "1.0", "hooks": []}
    for hook_name in manifest.get("hooks", []):
        validate_hook_name(hook_name)
    plugin = Plugin(
        tenant_id=tenant_id,
        name=name,
        description=description,
        version=version,
        webhook_url=webhook_url,
        manifest=manifest,
        enabled=True,
        config=config,
    )
    db.add(plugin)
    await db.flush()
    await db.refresh(plugin)
    return plugin


async def unregister_plugin(
    db: AsyncSession, plugin_id: int, tenant_id: int
) -> bool:
    """Remove a plugin. Returns True if it existed and was removed."""
    result = await db.execute(
        select(Plugin).where(Plugin.id == plugin_id, Plugin.tenant_id == tenant_id)
    )
    plugin = result.scalar_one_or_none()
    if not plugin:
        return False
    await db.delete(plugin)
    await db.flush()
    return True


async def get_plugin(
    db: AsyncSession, plugin_id: int, tenant_id: int
) -> Plugin | None:
    """Get a single plugin by ID, scoped to *tenant_id*."""
    result = await db.execute(
        select(Plugin).where(Plugin.id == plugin_id, Plugin.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def list_plugins(db: AsyncSession, tenant_id: int) -> list[Plugin]:
    """List all plugins for the given *tenant_id*."""
    result = await db.execute(
        select(Plugin)
        .where(Plugin.tenant_id == tenant_id)
        .order_by(Plugin.id)
    )
    return list(result.scalars().all())


async def set_plugin_enabled(
    db: AsyncSession, plugin_id: int, enabled: bool, tenant_id: int
) -> Plugin | None:
    """Enable or disable a plugin. Returns the updated plugin or None."""
    result = await db.execute(
        select(Plugin).where(Plugin.id == plugin_id, Plugin.tenant_id == tenant_id)
    )
    plugin = result.scalar_one_or_none()
    if not plugin:
        return None
    plugin.enabled = enabled
    await db.flush()
    await db.refresh(plugin)
    return plugin


async def update_plugin_config(
    db: AsyncSession,
    plugin_id: int,
    tenant_id: int,
    config: dict | None = None,
    description: str | None = None,
) -> Plugin | None:
    """Update a plugin's config and/or description. Returns the updated plugin or None."""
    result = await db.execute(
        select(Plugin).where(Plugin.id == plugin_id, Plugin.tenant_id == tenant_id)
    )
    plugin = result.scalar_one_or_none()
    if not plugin:
        return None
    if config is not None:
        plugin.config = config
    if description is not None:
        plugin.description = description
    await db.flush()
    await db.refresh(plugin)
    return plugin


# ─── Hook invocation ────────────────────────────────────────────────────────


async def call_hooks(
    db: AsyncSession,
    tenant_id: int,
    hook_name: str,
    context: dict,
    timeout: float = 5.0,
) -> list[dict]:
    """Call all enabled plugins subscribed to *hook_name* via their webhook URL.

    Args:
        db: Database session.
        tenant_id: Tenant scope.
        hook_name: Hook identifier (validated against ``HOOK_DEFINITIONS``).
        context: Data dict to pass to each plugin.
        timeout: HTTP request timeout in seconds.

    Returns:
        A list of result dicts — one per plugin — with ``plugin``, ``status``
        or ``error`` keys.
    """
    validate_hook_name(hook_name)

    import httpx

    # Find all enabled plugins whose manifest declares this hook
    result = await db.execute(
        select(Plugin).where(
            Plugin.tenant_id == tenant_id,
            Plugin.enabled == True,  # noqa: E712
        )
    )
    plugins = list(result.scalars().all())

    # Filter plugins whose manifest contains the hook name
    matched: list[Plugin] = []
    for plugin in plugins:
        hooks_list = plugin.manifest.get("hooks", [])
        if hook_name in hooks_list:
            matched.append(plugin)

    if not matched:
        return []

    results: list[dict] = []
    for plugin in matched:
        payload = {
            "hook": hook_name,
            "context": context,
            "plugin": plugin.name,
        }
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(plugin.webhook_url, json=payload)
                resp.raise_for_status()
            results.append({"plugin": plugin.name, "status": resp.status_code})
            plugin.last_called_at = datetime.now(timezone.utc)
            plugin.last_error = None
        except Exception as exc:
            logger.warning(
                "Plugin %s hook %s failed: %s", plugin.name, hook_name, exc
            )
            plugin.last_error = str(exc)[:500]
            results.append({"plugin": plugin.name, "error": str(exc)})

    await db.flush()
    return results
