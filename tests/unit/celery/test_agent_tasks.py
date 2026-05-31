"""Test Celery agent task dispatch (without real broker)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_crew_factory_returns_result():
    """Test that crew_factory.run_agent_for_task dispatches correctly."""
    from app.agents.crew_factory import run_agent_for_task

    with (
        patch("app.agents.crew_factory.async_session") as mock_sesh_factory,
        patch("app.agents.social_media.SocialMediaAgent.run") as mock_run,
    ):
        mock_run.return_value = {"summary": "Mocked result", "tweets": []}
        mock_session = AsyncMock()
        mock_sesh_factory.return_value.__aenter__.return_value = mock_session

        result = await run_agent_for_task(
            "social_media",
            {"title": "Post tweets", "description": None},
            {"company": {"name": "Test Co"}},
        )

    assert result["summary"] == "Mocked result"
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_crew_factory_raises_on_unknown_agent():
    from app.agents.crew_factory import run_agent_for_task
    with pytest.raises(ValueError, match="Unknown agent"):
        await run_agent_for_task("nonexistent_agent", {}, {})
