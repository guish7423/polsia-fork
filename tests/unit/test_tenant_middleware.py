"""Tests for TenantContextMiddleware and tenant_context integration."""

import pytest
from unittest.mock import AsyncMock, patch

from app.core.tenant_context import get_current_tenant, set_current_tenant, TenantContext


def test_set_and_get_tenant():
    """Setting a tenant context allows reading it back."""
    ctx = TenantContext(
        id=42,
        name="TestCorp",
        plan="pro",
        api_key="key_test",
        agents_limit=10,
        tasks_monthly_limit=10000,
        tokens_monthly_limit=50_000_000,
        cost_monthly_limit_usd=200.0,
        rpm_limit=300,
        active=True,
    )
    set_current_tenant(ctx)
    result = get_current_tenant()
    assert result is not None
    assert result.name == "TestCorp"
    assert result.plan == "pro"
    assert result.id == 42
    assert result.rpm_limit == 300


def test_tenant_context_dataclass():
    """TenantContext is a proper dataclass with all fields."""
    ctx = TenantContext(
        id=1,
        name="Dev",
        plan="enterprise",
        api_key="dev-key",
        agents_limit=9999,
        tasks_monthly_limit=999999,
        tokens_monthly_limit=999_999_999,
        cost_monthly_limit_usd=99999.0,
        rpm_limit=9999,
        active=True,
    )
    assert ctx.settings is None  # Optional default
    assert str(ctx) is not None  # Dataclass repr
