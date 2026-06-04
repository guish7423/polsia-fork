"""API key authentication via X-API-Key header — multi-tenant aware."""

from fastapi import Header, HTTPException

from app.config import settings
from app.core.database import async_session
from app.core.tenant_context import TenantContext
from app.services.tenant_service import get_tenant_by_api_key


async def verify_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
) -> str:
    """Verify the X-API-Key header. Returns str for backward compatibility."""
    # Dev key bypass
    if x_api_key == settings.api_key:
        return x_api_key

    # Look up tenant by API key
    async with async_session() as db:
        tenant = await get_tenant_by_api_key(db, x_api_key)
    if not tenant or not tenant.active:
        raise HTTPException(status_code=403, detail="Invalid or inactive API key")
    return x_api_key


async def verify_tenant(
    x_api_key: str = Header(..., alias="X-API-Key"),
) -> TenantContext:
    """Verify API key and return full tenant context (for new routes)."""
    # Dev key → enterprise context
    if x_api_key == settings.api_key:
        return TenantContext(
            id=0,
            name="Development",
            plan="enterprise",
            api_key=x_api_key,
            agents_limit=9999,
            tasks_monthly_limit=999999,
            tokens_monthly_limit=999_999_999,
            cost_monthly_limit_usd=99999.0,
            rpm_limit=9999,
            active=True,
        )

    # Look up tenant
    async with async_session() as db:
        tenant = await get_tenant_by_api_key(db, x_api_key)
    if not tenant or not tenant.active:
        raise HTTPException(status_code=403, detail="Invalid or inactive API key")

    return TenantContext(
        id=tenant.id,
        name=tenant.name,
        plan=tenant.plan,
        api_key=tenant.api_key,
        agents_limit=tenant.agents_limit,
        tasks_monthly_limit=tenant.tasks_monthly_limit,
        tokens_monthly_limit=tenant.tokens_monthly_limit,
        cost_monthly_limit_usd=tenant.cost_monthly_limit_usd,
        rpm_limit=tenant.rpm_limit,
        active=tenant.active,
        settings=tenant.settings,
    )
