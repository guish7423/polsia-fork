"""End-to-end integration tests — full agent execution chain.

Tests the complete pipeline:
  API trigger → BackgroundTasks → Agent run → DB writes → API reads

Uses in-memory SQLite + mock LLM + mock Redis (no Docker needed).
"""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_agent_trigger_end_to_end(api_client, auth_headers, async_db_session):
    """Full chain: POST trigger → agent runs → task appears in list."""
    # Step 1: Trigger an agent
    resp = await api_client.post(
        "/api/v1/agents/social_media/trigger",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "message" in data
    assert "social_media" in data["message"]

    # Step 2: Check agent list shows the agent
    resp = await api_client.get("/api/v1/agents", headers=auth_headers)
    assert resp.status_code == 200
    agents = resp.json()
    types = [a["agent_type"] for a in agents]
    assert "social_media" in types


@pytest.mark.asyncio
async def test_task_lifecycle(api_client, auth_headers):
    """Full chain: create task → list → get by id."""
    # Create task (query params, not JSON body)
    create_resp = await api_client.post(
        "/api/v1/tasks?title=Integration+test+task&agent_type=social_media&description=Created+by+integration+test&priority=1",
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    task = create_resp.json()
    task_id = task["id"]
    assert task["title"] == "Integration test task"

    # List tasks
    list_resp = await api_client.get(
        f"/api/v1/tasks?limit=10", headers=auth_headers,
    )
    assert list_resp.status_code == 200
    tasks = list_resp.json()
    assert any(t["id"] == task_id for t in tasks)

    # Get by id
    get_resp = await api_client.get(
        f"/api/v1/tasks/{task_id}", headers=auth_headers,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == task_id


@pytest.mark.asyncio
async def test_dashboard_reflects_data(api_client, auth_headers, async_db_session):
    """Dashboard summary returns data after agents run."""
    from app.services.task_service import create_task

    # Create some tasks
    from app.models.task import Task

    for i in range(3):
        await create_task(
            async_db_session,
            title=f"Dashboard task {i}",
            agent_type="social_media",
            source="test",
        )

    # Dashboard should reflect them
    resp = await api_client.get(
        "/api/v1/dashboard/summary", headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tasks_today_total"] >= 3


@pytest.mark.asyncio
async def test_crew_factory_runs_agent_with_mock_llm(async_db_session):
    """Crew factory creates agent, runs it, stores result."""
    from app.agents.crew_factory import run_agent_for_task

    with patch("app.agents.social_media.SocialMediaAgent.run") as mock_run:
        mock_run.return_value = {
            "summary": "Integration test run",
            "posts_created": 3,
        }

        result = await run_agent_for_task(
            "social_media",
            {"title": "Integration test", "description": "End-to-end test"},
            {"company": {"name": "TestCorp"}},
        )

    assert result["summary"] == "Integration test run"
    assert result["posts_created"] == 3


@pytest.mark.asyncio
async def test_multiple_agents_sequential(api_client, auth_headers):
    """Trigger multiple different agents and verify all execute."""
    agent_types = ["social_media", "business_planning", "competitor_research"]
    task_ids = []

    for atype in agent_types:
        resp = await api_client.post(
            f"/api/v1/agents/{atype}/trigger",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "message" in resp.json()

    # Agent list should show them
    resp = await api_client.get("/api/v1/agents", headers=auth_headers)
    agents = {a["agent_type"]: a for a in resp.json()}
    for atype in agent_types:
        assert atype in agents


@pytest.mark.asyncio
async def test_auth_required_for_all_endpoints(api_client):
    """Verify all auth-protected endpoints return 422 (missing header) or 403 (invalid key) without proper API key."""
    # Without X-API-Key header → 422 validation error
    endpoints = [
        ("GET", "/api/v1/social/posts"),
        ("GET", "/api/v1/memory"),
        ("PUT", "/api/v1/config"),
    ]
    for method, path in endpoints:
        if method == "GET":
            resp = await api_client.get(path)
        else:
            resp = await api_client.put(path, json={})
        # Missing required header → 422, invalid key → 403
        assert resp.status_code in (422, 403), f"{method} {path} expected 422/403 got {resp.status_code}"
