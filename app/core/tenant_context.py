"""Tenant context — ContextVar-based per-request tenant access."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional


@dataclass
class TenantContext:
    id: int
    name: str
    plan: str
    api_key: str
    agents_limit: int
    tasks_monthly_limit: int
    tokens_monthly_limit: int
    cost_monthly_limit_usd: float
    rpm_limit: int
    active: bool
    settings: Optional[dict] = None


_tenant: ContextVar[Optional[TenantContext]] = ContextVar("tenant", default=None)


def get_current_tenant() -> Optional[TenantContext]:
    """Get the current request's tenant context."""
    return _tenant.get()


def set_current_tenant(t: TenantContext) -> None:
    """Set the current request's tenant context."""
    _tenant.set(t)
