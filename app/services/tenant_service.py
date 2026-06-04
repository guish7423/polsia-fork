"""Tenant service — CRUD operations for Tenant model."""

from __future__ import annotations

import secrets
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant


async def create_tenant(
    db: AsyncSession,
    name: str,
    plan: str = "starter",
    api_key: Optional[str] = None,
) -> Tenant:
    """Create a new tenant with plan-based default limits."""
    if api_key is None:
        api_key = f"pol_{secrets.token_hex(16)}"

    defaults = Tenant.get_plan_defaults(plan)

    tenant = Tenant(
        name=name,
        plan=plan,
        api_key=api_key,
        agents_limit=defaults.get("agents_limit", 3),
        tasks_monthly_limit=defaults.get("tasks_monthly_limit", 1000),
        tokens_monthly_limit=defaults.get("tokens_monthly_limit", 10_000_000),
        cost_monthly_limit_usd=defaults.get("cost_monthly_limit_usd", 50.0),
        rpm_limit=defaults.get("rpm_limit", 60),
        active=True,
    )
    db.add(tenant)
    await db.flush()
    await db.refresh(tenant)
    return tenant


async def get_tenant(db: AsyncSession, tenant_id: int) -> Optional[Tenant]:
    """Get a tenant by ID."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()


async def get_tenant_by_api_key(
    db: AsyncSession, api_key: str
) -> Optional[Tenant]:
    """Look up a tenant by their API key."""
    result = await db.execute(
        select(Tenant).where(Tenant.api_key == api_key)
    )
    return result.scalar_one_or_none()


async def update_tenant(
    db: AsyncSession, tenant_id: int, **kwargs
) -> Optional[Tenant]:
    """Update a tenant's attributes."""
    tenant = await get_tenant(db, tenant_id)
    if tenant is None:
        return None
    for key, value in kwargs.items():
        if hasattr(tenant, key):
            setattr(tenant, key, value)
    await db.flush()
    await db.refresh(tenant)
    return tenant


async def list_tenants(
    db: AsyncSession, skip: int = 0, limit: int = 100
) -> list[Tenant]:
    """List all tenants with pagination."""
    result = await db.execute(
        select(Tenant).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


async def get_tenant_usage_summary(
    db: AsyncSession, tenant_id: int
) -> dict:
    """Get a summary of tenant resource usage (placeholder)."""
    tenant = await get_tenant(db, tenant_id)
    if tenant is None:
        return {}
    return {
        "tenant_id": tenant.id,
        "name": tenant.name,
        "plan": tenant.plan,
        "agents_limit": tenant.agents_limit,
        "tasks_monthly_limit": tenant.tasks_monthly_limit,
        "tokens_monthly_limit": tenant.tokens_monthly_limit,
        "cost_monthly_limit_usd": tenant.cost_monthly_limit_usd,
        "rpm_limit": tenant.rpm_limit,
    }


async def seed_default_tenant(db: AsyncSession) -> Tenant:
    """Create or return the default dev tenant."""
    existing = await get_tenant_by_api_key(db, "dev-key")
    if existing:
        return existing
    return await create_tenant(
        db,
        name="Default",
        plan="enterprise",
        api_key="dev-key",
    )
