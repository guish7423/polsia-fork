"""Test cross-model search service."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import select

from app.services.search_service import (
    search_all,
    _search_tasks,
    _search_agents,
    _search_alerts,
    _search_runs,
)


@pytest.mark.asyncio
async def test_search_all_returns_unified_format(async_db_session):
    """Verify the unified result format: [{type, id, title, description, url, score}]."""
    # Arrange — insert test data
    from app.models.task import Task
    from app.models.activity_log import ActivityLog
    from app.models.agent_run import AgentRun

    t1 = Task(id=1, tenant_id=1, title="Research competitors", description="Analyze top 10 competitors", agent_type="competitor_research", status="pending")
    t2 = Task(id=2, tenant_id=1, title="Send emails", description="Follow up with leads", agent_type="email_outreach", status="running")
    async_db_session.add(t1)
    async_db_session.add(t2)

    log = ActivityLog(id=1, agent_type="monitor", action="error", summary="API rate limit exceeded", level="error")
    async_db_session.add(log)

    run = AgentRun(id=1, tenant_id=1, agent_type="finance", task_id=1, status="completed")
    async_db_session.add(run)
    await async_db_session.flush()

    # Act
    results = await search_all(async_db_session, q="research", tenant_id=1)

    # Assert
    assert len(results) > 0
    for item in results:
        assert set(item.keys()) == {"type", "id", "title", "description", "url", "score"}
        assert item["type"] in ("task", "agent", "alert", "run")
        assert isinstance(item["score"], int)
        assert item["score"] >= 1


@pytest.mark.asyncio
async def test_search_tasks_fuzzy_match(async_db_session):
    """Tasks should match on title, description, and status via LIKE."""
    from app.models.task import Task

    tasks = [
        Task(id=10, tenant_id=1, title="Research competitors", description="Analyze market trends", agent_type="competitor_research", status="pending"),
        Task(id=11, tenant_id=1, title="Send weekly report", description="Research findings compilation", agent_type="finance", status="running"),
        Task(id=12, tenant_id=2, title="Other research", description="Unrelated", agent_type="competitor_research", status="pending"),
    ]
    for t in tasks:
        async_db_session.add(t)
    await async_db_session.flush()

    # Act — search "research" in tenant 1
    results = await _search_tasks(async_db_session, q="research", limit=20, tenant_id=1)

    # Assert — should find tasks 10 (title) and 11 (description) but not 12 (different tenant)
    found_ids = {r["id"] for r in results}
    assert 10 in found_ids, "Task with 'Research' in title should match"
    assert 11 in found_ids, "Task with 'Research' in description should match"
    assert 12 not in found_ids, "Task in different tenant should be excluded"


@pytest.mark.asyncio
async def test_search_tasks_exact_match_scores_higher(async_db_session):
    """Exact title matches should score higher than partial matches."""
    from app.models.task import Task

    tasks = [
        Task(id=20, tenant_id=1, title="Quarterly Report", description="Financial overview", agent_type="finance", status="pending"),
        Task(id=21, tenant_id=1, title="Send report to CEO", description="Quarterly summary", agent_type="orchestrator", status="pending"),
    ]
    for t in tasks:
        async_db_session.add(t)
    await async_db_session.flush()

    results = await _search_tasks(async_db_session, q="report", limit=20, tenant_id=1)

    # Task 20 title is an exact (starts-with-ish) match "Quarterly Report" contains "Report"
    # Task 21 description "Quarterly summary" doesn't contain "report"
    # Both have "report" somewhere, check scoring
    scores = {r["id"]: r["score"] for r in results}
    # Task 20 has "Report" in title — should have higher score
    assert scores[20] >= scores[21], "Task with keyword in title should score >= description-only match"


@pytest.mark.asyncio
async def test_search_agents_matches_descriptions(async_db_session):
    """Agent search matches agent_type and description from AGENT_DESCRIPTIONS."""
    results = _search_agents(q="finance", limit=20)

    assert len(results) > 0
    assert any(r["type"] == "agent" for r in results)
    # "finance" should match the finance agent
    finance = [r for r in results if r["id"] == "finance"]
    assert len(finance) > 0
    assert "Financial" in finance[0]["description"] or "finance" in finance[0]["title"]


@pytest.mark.asyncio
async def test_search_alerts_matches_message(async_db_session):
    """Alerts search matches summary and action fields."""
    from app.models.activity_log import ActivityLog

    logs = [
        ActivityLog(id=1, agent_type="monitor", action="error", summary="API rate limit exceeded", level="error"),
        ActivityLog(id=2, agent_type="orchestrator", action="warning", summary="Task quota at 90%", level="warning"),
        ActivityLog(id=3, agent_type="finance", action="info", summary="Daily report generated", level="info"),
    ]
    for log in logs:
        async_db_session.add(log)
    await async_db_session.flush()

    results = await _search_alerts(async_db_session, q="quota", limit=20, tenant_id=None)

    assert len(results) == 1
    assert results[0]["id"] == 2


@pytest.mark.asyncio
async def test_search_runs_matches_agent_type_and_status(async_db_session):
    """Runs search matches agent_type and status."""
    from app.models.agent_run import AgentRun

    runs = [
        AgentRun(id=1, tenant_id=1, agent_type="finance", status="completed", task_id=1),
        AgentRun(id=2, tenant_id=1, agent_type="orchestrator", status="running", task_id=2),
        AgentRun(id=3, tenant_id=1, agent_type="social_media", status="failed", task_id=3),
    ]
    for r in runs:
        async_db_session.add(r)
    await async_db_session.flush()

    results = await _search_runs(async_db_session, q="finance", limit=20, tenant_id=1)

    assert len(results) >= 1
    assert any(r["id"] == 1 for r in results)


@pytest.mark.asyncio
async def test_search_type_filtering(async_db_session):
    """The 'types' parameter should restrict which entity types are searched."""
    from app.models.task import Task

    t = Task(id=30, tenant_id=1, title="Research project", description="Deep research", agent_type="competitor_research", status="pending")
    async_db_session.add(t)
    await async_db_session.flush()

    # Only search agents — should not return tasks
    results = await search_all(async_db_session, q="research", types=["agents"], tenant_id=1)

    assert all(r["type"] == "agent" for r in results)
