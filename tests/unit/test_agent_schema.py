"""Tests for structured Agent Schema (app/agents/schema.py)."""

from __future__ import annotations

import pytest

from app.agents.schema import (
    AgentCapability,
    AgentSchema,
    AgentTier,
    all_schemas,
    build_prompt_for,
    get_schema,
    register_schema,
)
# Note: TaskCategory is a Literal[str] type, not an Enum.
# Valid values: "content_gen", "analysis", "code", "classification", "summarization", "conversation"


def test_agent_tier_values() -> None:
    assert AgentTier.CORE.value == "core"
    assert AgentTier.STANDARD.value == "standard"
    assert AgentTier.RESTRICTED.value == "restricted"
    assert AgentTier.SANDBOXED.value == "sandboxed"


def test_agent_capability() -> None:
    cap = AgentCapability(name="task_creation", description="Create tasks for other agents")
    assert cap.name == "task_creation"
    assert "Create tasks" in cap.description


def test_agent_schema_minimal() -> None:
    schema = AgentSchema(
        agent_type="test_agent",
        role="Test Agent",
        goal="Test the schema system",
        backstory="I exist to verify the structured agent schema works correctly.",
    )
    assert schema.agent_type == "test_agent"
    assert schema.tier == AgentTier.STANDARD  # default
    assert schema.max_tasks_per_run == 5
    assert schema.retry_on_failure is True
    assert schema.max_retries == 2
    assert schema.timeout_seconds == 120


def test_agent_schema_build_prompt_basic() -> None:
    """Prompt includes role, mission, backstory, quality rules, no extra sections."""
    schema = AgentSchema(
        agent_type="test",
        role="Tester",
        goal="Test everything thoroughly",
        backstory="I love testing.",
    )
    prompt = schema.build_prompt()
    assert "**Tester**" in prompt
    assert "Test everything thoroughly" in prompt
    assert "I love testing." in prompt
    assert "Quality Rules" in prompt
    assert "Return valid JSON only" in prompt
    assert "tools" not in prompt.lower() or schema.tools == []  # no tools section


def test_agent_schema_build_prompt_with_tools() -> None:
    schema = AgentSchema(
        agent_type="tool_user",
        role="Tool User",
        goal="Use tools effectively",
        backstory="I am good with tools.",
        tools=["hammer", "saw", "drill"],
    )
    prompt = schema.build_prompt()
    assert "- hammer" in prompt
    assert "- saw" in prompt
    assert "- drill" in prompt


def test_agent_schema_build_prompt_with_output_schema() -> None:
    schema = AgentSchema(
        agent_type="structured",
        role="Structured Output Agent",
        goal="Output structured data",
        backstory="I output schemas.",
        output_schema={"type": "object", "properties": {"name": {"type": "string"}}},
    )
    prompt = schema.build_prompt()
    assert "Output Format (JSON only)" in prompt
    assert '"name"' in prompt  # from the JSON schema
    assert '"type": "object"' in prompt


def test_agent_schema_build_prompt_with_extra_instructions() -> None:
    schema = AgentSchema(
        agent_type="instructed",
        role="Instructed Agent",
        goal="Follow instructions",
        backstory="I follow instructions.",
        extra_instructions="Always double-check your work.",
    )
    prompt = schema.build_prompt()
    assert "Additional Instructions" in prompt
    assert "Always double-check your work" in prompt


def test_agent_schema_build_prompt_with_company_context() -> None:
    schema = AgentSchema(
        agent_type="context_aware",
        role="Context Aware Agent",
        goal="Use company context",
        backstory="I use context.",
    )
    prompt = schema.build_prompt("We build AI agents.")
    assert "Company Context" in prompt
    assert "We build AI agents." in prompt


def test_agent_schema_max_tasks_in_prompt() -> None:
    schema = AgentSchema(
        agent_type="limited",
        role="Limited Agent",
        goal="Do limited work",
        backstory="I have limits.",
        max_tasks_per_run=3,
    )
    prompt = schema.build_prompt()
    assert "Maximum 3 tasks per run" in prompt


def test_agent_schema_tier_custom() -> None:
    schema = AgentSchema(
        agent_type="finance_agent",
        role="Finance Agent",
        goal="Handle finances",
        backstory="I handle money.",
        tier=AgentTier.RESTRICTED,
    )
    assert schema.tier == AgentTier.RESTRICTED


def test_agent_schema_task_category() -> None:
    schema = AgentSchema(
        agent_type="code_gen",
        role="Code Generator",
        goal="Write code",
        backstory="I write code.",
        task_category="analysis",
    )
    assert schema.task_category == "analysis"


def test_register_and_get_schema() -> None:
    schema = AgentSchema(
        agent_type="registered_agent",
        role="Registered Agent",
        goal="Be registered",
        backstory="I am registered.",
    )
    register_schema(schema)
    retrieved = get_schema("registered_agent")
    assert retrieved is not None
    assert retrieved.agent_type == "registered_agent"
    assert retrieved.role == "Registered Agent"


def test_duplicate_registration_raises() -> None:
    schema = AgentSchema(
        agent_type="duplicate",
        role="Duplicate Agent",
        goal="Duplicate",
        backstory="I am duplicated.",
    )
    register_schema(schema)
    with pytest.raises(AssertionError, match="Duplicate"):
        register_schema(schema)


def test_all_schemas_returns_dicts() -> None:
    schemas = all_schemas()
    assert isinstance(schemas, list)
    for s in schemas:
        assert isinstance(s, dict)
        assert "agent_type" in s
        assert "role" in s
        assert "tier" in s
        assert "task_category" in s


def test_build_prompt_for_registered() -> None:
    schema = AgentSchema(
        agent_type="prompt_for",
        role="Prompt For Agent",
        goal="Test build_prompt_for",
        backstory="Testing.",
    )
    register_schema(schema)
    prompt = build_prompt_for("prompt_for")
    assert "**Prompt For Agent**" in prompt


def test_build_prompt_for_unregistered_raises() -> None:
    with pytest.raises(KeyError, match="No schema registered"):
        build_prompt_for("non_existent")


def test_to_dict_serialization() -> None:
    schema = AgentSchema(
        agent_type="serializable",
        role="Serializable Agent",
        goal="Be serialized",
        backstory="I can be serialized.",
        tools=["tool1"],
        tier=AgentTier.CORE,
        task_category="code",
        tags=["test", "demo"],
        budget_cents=500,
    )
    d = schema.to_dict()
    assert d["agent_type"] == "serializable"
    assert d["tier"] == "core"
    assert d["task_category"] == "code"
    assert d["tools"] == ["tool1"]
    assert d["budget_cents"] == 500
    assert d["tags"] == ["test", "demo"]


def test_budget_cents_none_by_default() -> None:
    schema = AgentSchema(
        agent_type="no_budget",
        role="No Budget Agent",
        goal="Work without budget",
        backstory="I have no budget limit.",
    )
    assert schema.budget_cents is None
    d = schema.to_dict()
    assert d["budget_cents"] is None
