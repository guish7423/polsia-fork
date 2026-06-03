"""Model routing gateway — directs agent calls to the best LLM per task type.

This module integrates the new :class:`app.core.model_instance.ModelManager`
while preserving backward compatibility with the existing :class:`ModelProfile`
based API.  New code should prefer :func:`select_instance` /
:func:`fallback_instances` and the :class:`ModelManager` directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from app.core.model_instance import (
    CAPABILITY_RANK,
    AGENT_CATEGORY,
    ModelInstance,
    ModelManager,
    TaskCategory,
    agent_category as new_agent_category,
)

# ── Legacy ModelProfile (backward compatible) ────────────────────────────────


@dataclass
class ModelProfile:
    """An LLM endpoint that can handle one or more task categories.

    .. deprecated::
       Prefer :class:`app.core.model_instance.ModelInstance`.
    """

    name: str
    env_api_key: str
    base_url: str
    model: str
    capabilities: set[str] = field(default_factory=set)
    priority: int = 10
    requires_key: bool = True

    def api_key(self) -> str:
        return os.environ.get(self.env_api_key, "")

    @property
    def available(self) -> bool:
        if not self.requires_key:
            return True
        return bool(self.api_key())


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


# ── Legacy selectors (backward compatible — delegate internally) ─────────────


def select_model(task_category: str) -> ModelProfile | None:
    """Legacy: return the best available profile.

    .. deprecated::
       Use :func:`select_instance` instead.
    """
    sorted_profiles = sorted(PROFILES, key=lambda p: p.priority)
    for profile in sorted_profiles:
        if task_category not in profile.capabilities:
            continue
        if not profile.available:
            continue
        return profile
    return None


def fallback_chain(task_category: str) -> list[ModelProfile]:
    """Legacy: ordered list of available profiles.

    .. deprecated::
       Use :func:`fallback_instances` instead.
    """
    sorted_profiles = sorted(PROFILES, key=lambda p: p.priority)
    return [
        p for p in sorted_profiles
        if task_category in p.capabilities and p.available
    ]


def agent_category(agent_type: str) -> TaskCategory:
    """Return the task category for *agent_type*, defaulting to ``analysis``."""
    return new_agent_category(agent_type)


def build_request_kwargs(
    profile: ModelProfile,
    system_prompt: str | None = None,
    json_mode: bool = True,
) -> dict:
    """Legacy: return ``dict`` suitable for ``httpx.AsyncClient.post(**kwargs)``.

    .. deprecated::
       Use :meth:`ModelInstance.chat` instead — it handles headers, body
       construction, rate limiting, and token tracking automatically.
    """
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


# ── New API: ModelInstance-based selectors ───────────────────────────────────

_manager: ModelManager | None = None


def _get_manager() -> ModelManager:
    """Lazy-init singleton manager.

    Use :func:`set_manager` to inject a customised manager (e.g. in tests).
    """
    global _manager
    if _manager is None:
        _manager = ModelManager.get_default()
    return _manager


def set_manager(manager: ModelManager | None) -> None:
    """Set the global manager (useful for testing or custom configuration).

    Pass ``None`` to reset to the default singleton on the next call.
    """
    global _manager
    _manager = manager


def select_instance(task_category: str) -> ModelInstance | None:
    """Return the best available :class:`ModelInstance` for *task_category*.

    This is the new preferred routing method.  It delegates to the
    :class:`ModelManager` singleton.
    """
    return _get_manager().select(task_category)


def fallback_instances(task_category: str) -> list[ModelInstance]:
    """Return all available instances matching *task_category* (best first)."""
    return _get_manager().fallback_chain(task_category)


def get_manager() -> ModelManager:
    """Return the current :class:`ModelManager` singleton."""
    return _get_manager()
