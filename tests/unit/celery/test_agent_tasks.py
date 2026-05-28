"""Test Celery agent task dispatch and crew factory integration."""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_crew_factory_returns_result():
    """Test crew_factory.run_agent_for_task dispatches async agent correctly."""
    from app.agents.crew_factory import run_agent_for_task

    with (
        patch("app.agents.crew_factory.async_session") as mock_session,
        patch("app.agents.social_media.SocialMediaAgent.run") as mock_run,
    ):
        mock_run.return_value = {"summary": "Mocked result", "tweets": []}
        mock_session.return_value.__aenter__.return_value = AsyncMock()

        result = await run_agent_for_task(
            "social_media",
            {"title": "Post tweets", "description": None},
            {"company": {"name": "Test Co"}},
        )

    assert result["summary"] == "Mocked result"


@pytest.mark.asyncio
async def test_crew_factory_raises_on_unknown_agent():
    """Test that unknown agent type raises ValueError."""
    from app.agents.crew_factory import run_agent_for_task

    with pytest.raises(ValueError, match="Unknown agent"):
        await run_agent_for_task("nonexistent_agent", {}, {})


@pytest.mark.asyncio
async def test_crew_factory_all_known_agents():
    """Test that all registered agent types can be instantiated."""
    """Test that known agent types can be instantiated from agent_map."""
    from app.agents import agent_map

    from app.agents.social_media import SocialMediaAgent
    assert issubclass(agent_map["social_media"], SocialMediaAgent)


@pytest.mark.asyncio
async def test_run_agent_task_imports():
    """Test the Celery run_agent task imports correctly."""
    from celery_app.tasks.agent_tasks import run_agent

    assert run_agent is not None
    assert hasattr(run_agent, "delay")
