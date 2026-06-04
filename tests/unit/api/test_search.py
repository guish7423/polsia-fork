"""Test GET /api/v1/search endpoint."""
import pytest


@pytest.mark.asyncio
async def test_search_returns_results(api_client, auth_headers, async_db_session):
    """Search returns unified results from multiple entity types."""
    from app.models.task import Task

    t = Task(id=1, tenant_id=1, title="Research competitors", description="Market analysis", agent_type="competitor_research", status="pending")
    async_db_session.add(t)
    await async_db_session.flush()

    resp = await api_client.get(
        "/api/v1/search?q=research",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    # Check unified format
    for item in data:
        assert "type" in item
        assert "id" in item
        assert "title" in item
        assert "description" in item
        assert "url" in item
        assert "score" in item


@pytest.mark.asyncio
async def test_search_type_filter(api_client, auth_headers, async_db_session):
    """Search with type filter should only return specified types."""
    from app.models.task import Task

    t = Task(id=2, tenant_id=1, title="Finance report", description="Monthly analysis", agent_type="finance", status="pending")
    async_db_session.add(t)
    await async_db_session.flush()

    # Only search agents — should not include tasks
    resp = await api_client.get(
        "/api/v1/search?q=finance&types=agents",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(r["type"] == "agent" for r in data)


@pytest.mark.asyncio
async def test_search_empty_query(api_client, auth_headers):
    """Empty query returns empty list."""
    resp = await api_client.get(
        "/api/v1/search?q=",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_search_limit(api_client, auth_headers, async_db_session):
    """Limit parameter should cap results."""
    from app.models.task import Task

    for i in range(25):
        t = Task(id=100 + i, tenant_id=1, title=f"Task {i}", description=f"Description {i}", agent_type="orchestrator", status="pending")
        async_db_session.add(t)
    await async_db_session.flush()

    resp = await api_client.get(
        "/api/v1/search?q=task&limit=5",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) <= 5
