"""Structured Agent Schema — CrewAI-style typed definitions.

Each agent is defined as a dataclass with:
- ``role`` — what this agent is (e.g. "CEO Orchestrator")
- ``goal`` — what this agent aims to achieve
- ``backstory`` — context and personality
- ``tools`` — what capabilities this agent can use
- ``task_category`` — which model profile to use
- ``prompt_template`` — how to build the system prompt from the schema

This replaces ad‑hoc prompt strings with inspectable, serializable definitions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Any

from app.services.model_router import TaskCategory


class AgentTier(Enum):
    """Risk / privilege tier for sandbox gating."""
    CORE = "core"           # Unrestricted (orchestrator, monitor, evolution)
    STANDARD = "standard"   # Normal (social_media, code_gen, intel…)
    RESTRICTED = "restricted"  # Needs approval (finance, deploy, order_fulfiller)
    SANDBOXED = "sandboxed"    # Always blocks (canary, experimental)


@dataclass
class AgentCapability:
    """A specific capability / tool an agent can use."""
    name: str
    description: str


@dataclass
class AgentSchema:
    """Structured agent definition — the CrewAI equivalent for CrossWave.

    Usage::

        ORCHESTRATOR = AgentSchema(
            agent_type="orchestrator",
            role="CEO Orchestrator",
            goal="Create daily plans and coordinate all agents",
            backstory="You are the CEO of CrossWave…",
            tools=["task_creation", "reporting"],
            task_category="analysis",
            tier=AgentTier.CORE,
        )
        system_prompt = ORCHESTRATOR.build_prompt()  # → str
    """
    agent_type: str
    role: str
    goal: str
    backstory: str
    tools: list[str] = field(default_factory=list)
    task_category: TaskCategory = "analysis"
    tier: AgentTier = AgentTier.STANDARD
    output_schema: dict[str, Any] | None = None
    extra_instructions: str | None = None
    tags: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    """List of capabilities this agent provides (e.g. 'web_search', 'content_creation', 'financial_analysis')."""
    max_tasks_per_run: int = 5
    """Maximum tasks this agent can create in a single run."""
    retry_on_failure: bool = True
    max_retries: int = 2
    budget_cents: int | None = None
    """Per-run cost cap in USD cents (None = no cap)."""
    timeout_seconds: int = 120
    """Hard timeout for a single run."""

    def build_prompt(self, company_context: str | None = None) -> str:
        """Build the full system prompt from structured fields.

        This generates a prompt with the same quality as the hand‑written ones
        in ``prompts.py``, but driven entirely by schema fields.
        """
        lines = [
            f"You are the **{self.role}** for CrossWave — an AI-native company helping Chinese entrepreneurs go global.",
            "",
            f"## Mission",
            self.goal,
            "",
            f"## Backstory",
            self.backstory,
        ]

        if self.tools:
            lines += [
                "",
                "## Tools & Capabilities",
                *[f"- {t}" for t in self.tools],
            ]

        if self.output_schema:
            lines += [
                "",
                "## Output Format (JSON only)",
                json.dumps(self.output_schema, indent=2, ensure_ascii=False),
            ]

        if self.extra_instructions:
            lines += [
                "",
                "## Additional Instructions",
                self.extra_instructions,
            ]

        lines += [
            "",
            "## Quality Rules",
            "- Return valid JSON only (no markdown fences)",
            "- Be honest — never fabricate data",
            f"- Maximum {self.max_tasks_per_run} tasks per run",
            "- Focus on actionable outcomes, not busywork",
        ]

        if company_context:
            lines += [
                "",
                "## Company Context",
                company_context,
            ]

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON‑compatible dict (for HQ display)."""
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        d["tier"] = self.tier.value
        d["task_category"] = self.task_category
        return d


# ─── Helpers ────────────────────────────────────────────────────────────────────

_registry: dict[str, AgentSchema] = {}


def register_schema(schema: AgentSchema) -> AgentSchema:
    """Register an AgentSchema in the global registry."""
    assert schema.agent_type not in _registry, f"Duplicate agent_type: {schema.agent_type}"
    _registry[schema.agent_type] = schema
    return schema


def get_schema(agent_type: str) -> AgentSchema | None:
    """Look up a schema by agent_type."""
    return _registry.get(agent_type)


def all_schemas() -> list[dict[str, Any]]:
    """Return all registered schemas as dicts (for HQ API)."""
    return [s.to_dict() for s in _registry.values()]


def build_prompt_for(agent_type: str, company_context: str | None = None) -> str:
    """Convenience: build prompt for a given agent type."""
    schema = get_schema(agent_type)
    if schema is None:
        raise KeyError(f"No schema registered for {agent_type!r}")
    return schema.build_prompt(company_context)
