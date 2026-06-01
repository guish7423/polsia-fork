"""Model routing gateway — directs agent calls to the best LLM per task type.

Each `ModelProfile` maps to an LLM endpoint.  The router selects the best
profile for a given task category based on capability rank and availability.
If the primary model fails, the caller falls through the chain.

Task categories
---------------
- content_gen       : creative writing, blog posts, social copy
- analysis          : data analysis, metrics, business logic
- code              : code generation, debugging, deployment scripts
- classification    : scoring, ranking, filtering, order evaluation
- summarization     : briefings, reports, market intelligence
- conversation      : customer support, lead nurturing, email outreach

Agent → category mapping is defined in AGENT_CATEGORY.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

TaskCategory = Literal[
    "content_gen", "analysis", "code", "classification", "summarization", "conversation"
]

CAPABILITY_RANK: dict[str, int] = {
    "content_gen": 1,
    "conversation": 2,
    "summarization": 3,
    "analysis": 4,
    "classification": 5,
    "code": 6,
}

# ── Agent → category mapping ────────────────────────────────────────────────
# Every registered agent type is assigned a task category.  The router uses
# this to select the optimal model profile for each call.
AGENT_CATEGORY: dict[str, TaskCategory] = {
    "orchestrator": "analysis",
    "social_media": "content_gen",
    "competitor_research": "analysis",
    "business_planning": "analysis",
    "deployment": "code",
    "finance": "analysis",
    "ads_management": "analysis",
    "email_outreach": "conversation",
    "code_generation": "code",
    "customer_support": "conversation",
    "order_scanner": "classification",
    "order_fulfiller": "analysis",
    "lead_nurturing": "conversation",
    "deploy_agent": "code",
    "monitor": "analysis",
    "evolution": "analysis",
    "market_intel": "summarization",
}


# ── Model profiles ──────────────────────────────────────────────────────────

@dataclass
class ModelProfile:
    """An LLM endpoint that can handle one or more task categories."""

    name: str
    env_api_key: str
    base_url: str
    model: str
    capabilities: set[str] = field(default_factory=set)
    """Task categories this model is optimised for."""
    priority: int = 10
    """Lower = tried first when multiple profiles match."""
    requires_key: bool = True

    def api_key(self) -> str:
        return os.environ.get(self.env_api_key, "")

    @property
    def available(self) -> bool:
        if not self.requires_key:
            return True
        return bool(self.api_key())


# ── Build profile list from available env vars ──────────────────────────────

PROFILES: list[ModelProfile] = [
    ModelProfile(
        name="DeepSeek V4 Flash",
        env_api_key="DEEPSEEK_API_KEY",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
        capabilities={"analysis", "content_gen", "classification", "summarization", "conversation"},
        priority=1,
    ),
    ModelProfile(
        name="DeepSeek V4 Flash (via LLM_API_KEY)",
        env_api_key="LLM_API_KEY",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
        capabilities={"analysis", "content_gen", "classification", "summarization", "conversation"},
        priority=2,
    ),
    ModelProfile(
        name="Volc Engine Doubao-pro",
        env_api_key="VOLC_ENGINE_API_KEY",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        model="doubao-pro-32k",
        capabilities={"content_gen", "analysis", "summarization", "conversation"},
        priority=3,
    ),
    ModelProfile(
        name="Volc Engine Doubao-lite",
        env_api_key="VOLC_ENGINE_API_KEY",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        model="doubao-lite-32k",
        capabilities={"classification", "summarization"},
        priority=4,
    ),
    ModelProfile(
        name="Mock (no API key)",
        env_api_key="",
        base_url="",
        model="mock",
        capabilities={"analysis", "content_gen", "code", "classification", "summarization", "conversation"},
        priority=99,
        requires_key=False,
    ),
]


def select_model(task_category: TaskCategory) -> ModelProfile | None:
    """Return the best *available* model profile for *task_category*.

    Profiles are sorted by priority (lower first); the first available
    profile whose capabilities include *task_category* wins.
    Returns ``None`` only if no profile (including Mock) is configured.
    """
    sorted_profiles = sorted(PROFILES, key=lambda p: p.priority)
    for profile in sorted_profiles:
        if task_category not in profile.capabilities:
            continue
        if not profile.available:
            continue
        return profile
    return None


def fallback_chain(task_category: TaskCategory) -> list[ModelProfile]:
    """Ordered list of available profiles for *task_category* (best first).

    The caller can iterate through this list on failure.
    """
    sorted_profiles = sorted(PROFILES, key=lambda p: p.priority)
    return [
        p for p in sorted_profiles
        if task_category in p.capabilities and p.available
    ]


def agent_category(agent_type: str) -> TaskCategory:
    """Return the task category for *agent_type*, defaulting to ``analysis``."""
    return AGENT_CATEGORY.get(agent_type, "analysis")


# ── Convenience: build headers / body for a profile ─────────────────────────

def build_request_kwargs(
    profile: ModelProfile,
    system_prompt: str | None = None,
    json_mode: bool = True,
) -> dict:
    """Return ``dict`` suitable for ``httpx.AsyncClient.post(**kwargs)``."""
    headers = {
        "Authorization": f"Bearer {profile.api_key()}",
        "Content-Type": "application/json",
    }
    body: dict = {
        "model": profile.model,
        "messages": [],
        "temperature": 0.7,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if system_prompt:
        body["messages"].append({"role": "system", "content": system_prompt})
    return {
        "url": f"{profile.base_url}/chat/completions",
        "headers": headers,
        "json": body,
        "timeout": 120,
    }
