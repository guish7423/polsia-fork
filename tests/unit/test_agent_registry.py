"""Tests for agent registry — all 17+ agents defined as structured schemas."""

from __future__ import annotations

from app.agents.registry import agent_count, ensure_registered, get_schema
from app.agents.schema import AgentTier


def test_registry_initializes() -> None:
    """Calling ensure_registered() is idempotent and returns all agents."""
    ensure_registered()
    assert agent_count() >= 16  # at least 16 agents registered


def test_orchestrator_schema() -> None:
    schema = get_schema("orchestrator")
    assert schema is not None
    assert schema.role == "CEO Orchestrator"
    assert schema.tier == AgentTier.CORE
    assert schema.max_tasks_per_run == 10


def test_finance_schema_restricted() -> None:
    schema = get_schema("finance")
    assert schema is not None
    assert schema.tier == AgentTier.RESTRICTED
    assert "track every dollar" in schema.backstory.lower()
    assert schema.task_category == "analysis"


def test_order_scanner_schema() -> None:
    schema = get_schema("order_scanner")
    assert schema is not None
    assert schema.tier == AgentTier.RESTRICTED
    assert schema.task_category == "classification"
    assert schema.timeout_seconds == 180


def test_all_agents_have_prompt() -> None:
    ensure_registered()
    for schema in [get_schema(t) for t in (
        "orchestrator", "evolution", "monitor", "market_intel",
        "social_media", "competitor_research", "business_planning",
        "code_generation", "customer_support", "email_outreach",
        "ads_management", "lead_nurturing",
        "finance", "deployment", "deploy_agent", "order_scanner",
        "order_fulfiller",
    )]:
        assert schema is not None, f"Missing schema for agent"
        prompt = schema.build_prompt()
        assert len(prompt) > 200, f"Prompt too short for {schema.agent_type}"
        assert schema.role in prompt, f"Role not in prompt for {schema.agent_type}"


def test_each_schema_has_backstory() -> None:
    ensure_registered()
    for agent_type in [
        "orchestrator", "evolution", "monitor", "market_intel",
        "social_media", "competitor_research", "business_planning",
        "code_generation", "customer_support", "email_outreach",
        "ads_management", "lead_nurturing",
        "finance", "deployment", "deploy_agent", "order_scanner",
        "order_fulfiller",
    ]:
        schema = get_schema(agent_type)
        assert schema is not None
        assert schema.backstory, f"Empty backstory for {agent_type}"
        assert len(schema.backstory) > 50, f"Backstory too short for {agent_type}"


def test_core_agents_unrestricted() -> None:
    for agent_type in ["orchestrator", "evolution", "monitor", "market_intel"]:
        schema = get_schema(agent_type)
        assert schema is not None
        assert schema.tier == AgentTier.CORE, f"{agent_type} should be CORE"
        assert schema.max_retries >= 2


def test_restricted_agents_have_sandbox_implications() -> None:
    for agent_type in ["finance", "deployment", "deploy_agent", "order_scanner", "order_fulfiller"]:
        schema = get_schema(agent_type)
        assert schema is not None
        assert schema.tier == AgentTier.RESTRICTED, f"{agent_type} should be RESTRICTED"


def test_all_agents_serializable() -> None:
    ensure_registered()
    from app.agents.schema import all_schemas
    schemas = all_schemas()
    for s in schemas:
        assert "agent_type" in s
        assert "role" in s
        assert "tier" in s
        assert "task_category" in s
        assert "tools" in s
        assert isinstance(s["tools"], list)
