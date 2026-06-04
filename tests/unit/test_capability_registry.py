"""Test capability registry — lookup, filtering, cache invalidation."""

import pytest

from app.services.capability_registry import (
    find_agents_by_capability,
    agent_capabilities,
    all_capabilities,
    invalidate_capability_cache,
)


@pytest.fixture(autouse=True)
def _reset_cache():
    invalidate_capability_cache()
    yield
    invalidate_capability_cache()


class TestFindAgentsByCapability:
    def test_find_web_search(self):
        matches = find_agents_by_capability("web_search")
        assert len(matches) >= 1
        types = [m["agent_type"] for m in matches]
        assert "market_intel" in types

    def test_find_financial_analysis(self):
        matches = find_agents_by_capability("financial_analysis")
        assert len(matches) >= 1
        assert matches[0]["agent_type"] == "finance"

    def test_find_unknown_capability(self):
        matches = find_agents_by_capability("quantum_computing")
        assert matches == []

    def test_find_with_tier_filter(self):
        matches = find_agents_by_capability("web_search", min_tier="core")
        # market_intel is CORE tier, so it should match
        assert len(matches) >= 1


class TestAgentCapabilities:
    def test_orchestrator_capabilities(self):
        caps = agent_capabilities("orchestrator")
        assert "planning" in caps
        assert "delegation" in caps

    def test_unknown_agent(self):
        caps = agent_capabilities("nonexistent_agent")
        assert caps == []


class TestAllCapabilities:
    def test_all_capabilities_structure(self):
        caps = all_capabilities()
        assert isinstance(caps, dict)
        assert "web_search" in caps
        assert "financial_analysis" in caps
        assert len(caps) > 5

    def test_cache_invalidation(self):
        caps1 = all_capabilities()
        invalidate_capability_cache()
        caps2 = all_capabilities()
        assert caps1 == caps2  # same data, but recalculated
