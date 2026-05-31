"""Test company_service — get_company and recommendations."""
import pytest

from app.models.company_config import CompanyConfig
from app.services.company_service import get_company, update_company


@pytest.mark.asyncio
async def test_get_company_empty_db(async_db_session):
    result = await get_company(async_db_session)
    assert result is None


@pytest.mark.asyncio
async def test_get_company_with_record(async_db_session):
    company = CompanyConfig(
        name="Test Co",
        mission="Make testing great",
        kpis={"mrr_usd": 1000},
    )
    async_db_session.add(company)
    await async_db_session.commit()

    result = await get_company(async_db_session)
    assert result is not None
    assert result.name == "Test Co"
    assert result.kpis["mrr_usd"] == 1000


@pytest.mark.asyncio
async def test_update_company(async_db_session):
    company = CompanyConfig(name="Old Name")
    async_db_session.add(company)
    await async_db_session.commit()

    updated = await update_company(async_db_session, company.id, name="New Name", mission="Updated")
    assert updated is not None
    assert updated.name == "New Name"
    assert updated.mission == "Updated"


@pytest.mark.asyncio
async def test_update_company_not_found(async_db_session):
    result = await update_company(async_db_session, 99999, name="Ghost")
    assert result is None
