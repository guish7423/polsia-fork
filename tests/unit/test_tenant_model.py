"""Tests for Tenant model and tenant_service."""

import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_create_tenant(async_db_session):
    from app.services.tenant_service import create_tenant

    tenant = await create_tenant(async_db_session, name="Acme Corp", plan="starter")
    assert tenant.id is not None
    assert tenant.plan == "starter"
    assert tenant.active is True


@pytest.mark.asyncio
async def test_lookup_by_api_key(async_db_session):
    from app.services.tenant_service import create_tenant, get_tenant_by_api_key

    tenant = await create_tenant(async_db_session, name="Acme", api_key="key_abc")
    found = await get_tenant_by_api_key(async_db_session, "key_abc")
    assert found is not None
    assert found.name == "Acme"


@pytest.mark.asyncio
async def test_unknown_key_returns_none(async_db_session):
    from app.services.tenant_service import get_tenant_by_api_key

    result = await get_tenant_by_api_key(async_db_session, "nope")
    assert result is None


@pytest.mark.asyncio
async def test_tenant_default_limits(async_db_session):
    from app.services.tenant_service import create_tenant

    t = await create_tenant(async_db_session, name="Test", plan="starter")
    assert t.agents_limit == 3
    assert t.tasks_monthly_limit == 1000
    assert t.tokens_monthly_limit == 10_000_000
    assert t.rpm_limit == 60


@pytest.mark.asyncio
async def test_tenant_plan_tiers(async_db_session):
    from app.services.tenant_service import create_tenant

    pro = await create_tenant(async_db_session, name="Pro", plan="pro")
    assert pro.agents_limit == 10
    assert pro.tasks_monthly_limit == 10_000

    ent = await create_tenant(async_db_session, name="Enterprise", plan="enterprise")
    assert ent.agents_limit == 50
    assert ent.tasks_monthly_limit == 100_000


@pytest.mark.asyncio
async def test_get_tenant(async_db_session):
    from app.services.tenant_service import create_tenant, get_tenant

    t = await create_tenant(async_db_session, name="FindMe", plan="starter")
    found = await get_tenant(async_db_session, t.id)
    assert found is not None
    assert found.name == "FindMe"


@pytest.mark.asyncio
async def test_get_tenant_not_found(async_db_session):
    from app.services.tenant_service import get_tenant

    result = await get_tenant(async_db_session, 99999)
    assert result is None


@pytest.mark.asyncio
async def test_update_tenant(async_db_session):
    from app.services.tenant_service import create_tenant, update_tenant

    t = await create_tenant(async_db_session, name="Before", plan="starter")
    updated = await update_tenant(async_db_session, t.id, name="After")
    assert updated.name == "After"
    assert updated.id == t.id


@pytest.mark.asyncio
async def test_list_tenants(async_db_session):
    from app.services.tenant_service import create_tenant, list_tenants

    await create_tenant(async_db_session, name="A", plan="starter")
    await create_tenant(async_db_session, name="B", plan="pro")

    tenants = await list_tenants(async_db_session)
    assert len(tenants) >= 2


@pytest.mark.asyncio
async def test_seed_default_tenant(async_db_session):
    from app.services.tenant_service import seed_default_tenant

    tenant = await seed_default_tenant(async_db_session)
    assert tenant.name == "Default"
    assert tenant.plan == "enterprise"
    assert tenant.active is True
