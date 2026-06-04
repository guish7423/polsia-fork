"""TenantContextMiddleware — sets per-request tenant from X-API-Key."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.core.database import async_session
from app.core.tenant_context import (
    TenantContext,
    set_current_tenant,
)
from app.services.tenant_service import get_tenant_by_api_key


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Extract tenant from X-API-Key and set in ContextVar."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        api_key = request.headers.get("x-api-key", "")
        if api_key == settings.api_key:
            set_current_tenant(
                TenantContext(
                    id=0,
                    name="Development",
                    plan="enterprise",
                    api_key=api_key,
                    agents_limit=9999,
                    tasks_monthly_limit=999999,
                    tokens_monthly_limit=999_999_999,
                    cost_monthly_limit_usd=99999.0,
                    rpm_limit=9999,
                    active=True,
                )
            )
        elif api_key:
            async with async_session() as db:
                tenant = await get_tenant_by_api_key(db, api_key)
            if tenant and tenant.active:
                set_current_tenant(
                    TenantContext(
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
                )
        return await call_next(request)
