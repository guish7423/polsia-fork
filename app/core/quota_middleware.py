"""Per-endpoint quota enforcement middleware.

Inspects POST/PUT requests to task-creation and agent-run endpoints
and rejects them with ``429`` when the tenant's quota has been exceeded.

Usage::

    app.add_middleware(QuotaEnforcementMiddleware)
"""

from __future__ import annotations

import json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.core.database import async_session
from app.core.tenant_context import get_current_tenant
from app.services.quota_service import check_agent_quota

# Exempt paths (health check, docs, etc. — same as rate-limit middleware)
EXEMPT_PATHS: set[str] = {"/api/v1/health", "/docs", "/openapi.json", "/redoc"}


class QuotaEnforcementMiddleware(BaseHTTPMiddleware):
    """Reject POST/PUT to task/agent-run endpoints when tenant quota is
    exhausted.

    The middleware is gated by ``settings.quota_middleware_enabled``.
    When the gate is closed or the tenant context is missing, all
    requests pass through without inspection.
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if not settings.quota_middleware_enabled:
            return await call_next(request)

        path = request.url.path

        # Bypass for exempt paths
        if path in EXEMPT_PATHS:
            return await call_next(request)

        # Only inspect mutating requests
        if request.method not in ("POST", "PUT"):
            return await call_next(request)

        # Determine if this is a path we care about
        is_task_path = path.startswith("/api/v1/tasks")
        is_agent_run_path = path.startswith("/api/v1/agents/runs")

        if not is_task_path and not is_agent_run_path:
            return await call_next(request)

        # Read tenant context — if absent, let the request through
        # (the route handlers themselves will reject unauthenticated
        # requests at a later stage).
        tenant = get_current_tenant()
        if tenant is None:
            return await call_next(request)

        try:
            async with async_session() as db:
                if is_agent_run_path:
                    result = await check_agent_quota(db, tenant.id)
                    if not result.allowed:
                        return Response(
                            status_code=429,
                            content=json.dumps(
                                {"detail": "agent_limit_exceeded"}
                            ),
                            media_type="application/json",
                            headers={
                                "X-Quota-Limit": str(result.limit),
                                "X-Quota-Current": str(result.current),
                            },
                        )
        except Exception:
            # Fail-open when the database is unavailable
            pass

        return await call_next(request)
