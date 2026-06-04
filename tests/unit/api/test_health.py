"""Test GET /api/v1/dashboard/health — aggregated system health."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.agent_run import AgentRun
from app.models.model_call import ModelCall
from app.models.task import Task


@pytest.mark.asyncio
async def test_health_healthy(api_client, auth_headers):
    """Empty DB should return overall=healthy with all checks green."""
    resp = await api_client.get("/api/v1/dashboard/health", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall"] == "healthy"
    assert data["checks"]["agents"]["status"] == "healthy"
    assert data["checks"]["tasks"]["status"] == "healthy"
    assert data["checks"]["quota"]["status"] == "healthy"
    assert data["checks"]["cost"]["status"] == "healthy"
    assert "last_updated" in data["checks"]


@pytest.mark.asyncio
async def test_health_agent_degraded(api_client, auth_headers, async_db_session):
    """Agent with error status should make overall=degraded."""
    now = datetime.now(timezone.utc)
    async_db_session.add(AgentRun(
        tenant_id=0, agent_type="orchestrator", status="error",
        run_type="task", started_at=now,
    ))
    async_db_session.add(AgentRun(
        tenant_id=0, agent_type="finance", status="running",
        run_type="task", started_at=now,
    ))
    await async_db_session.commit()

    resp = await api_client.get("/api/v1/dashboard/health", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall"] == "degraded"
    assert data["checks"]["agents"]["status"] == "degraded"
    assert data["checks"]["agents"]["errored"] >= 1
    assert data["checks"]["agents"]["running"] >= 1


@pytest.mark.asyncio
async def test_health_tasks_degraded(api_client, auth_headers, async_db_session):
    """More than 5 failed tasks in 24h should make overall=degraded."""
    now = datetime.now(timezone.utc)
    for i in range(6):
        async_db_session.add(Task(
            tenant_id=0, title=f"Failed task {i}", agent_type="orchestrator",
            status="failed", created_at=now,
        ))
    await async_db_session.commit()

    resp = await api_client.get("/api/v1/dashboard/health", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall"] == "degraded"
    assert data["checks"]["tasks"]["status"] == "degraded"
    assert data["checks"]["tasks"]["failed_24h"] >= 6


@pytest.mark.asyncio
async def test_health_cost_warning(api_client, auth_headers, async_db_session):
    """Cost spike >50% vs yesterday should show warning, overall stays healthy."""
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(hours=36)

    # Yesterday: $1.00 in costs
    async_db_session.add(ModelCall(
        tenant_id=0, provider="openai", model="gpt-4",
        input_tokens=100, output_tokens=50, cost_usd=1.0,
        duration_ms=500, success=True, created_at=yesterday,
    ))
    # Today: $2.00 (>50% increase from $1.00)
    async_db_session.add(ModelCall(
        tenant_id=0, provider="openai", model="gpt-4",
        input_tokens=200, output_tokens=100, cost_usd=2.0,
        duration_ms=500, success=True, created_at=now,
    ))
    await async_db_session.commit()

    resp = await api_client.get("/api/v1/dashboard/health", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["checks"]["cost"]["status"] == "warning"
    assert data["overall"] == "healthy"  # cost warning alone doesn't degrade overall
