"""Plugin extension points — hook definitions for agent execution pipeline.

Each hook defines what context it receives and whether it runs synchronously
(webhook timeout is logged but doesn't block the main flow).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class HookDef:
    """Definition of a single extension point."""

    description: str
    context_keys: set[str]
    sync: bool
    """When True, the webhook request has a short timeout but does not block
    the main flow — timeout errors are logged and swallowed."""


# ─── Hook Registry ──────────────────────────────────────────────────────────

HOOK_DEFINITIONS: dict[str, HookDef] = {
    "before_agent_run": HookDef(
        description="Agent 执行前触发",
        context_keys={"agent_type", "task_id", "tenant_id", "input_context"},
        sync=True,
    ),
    "after_agent_run": HookDef(
        description="Agent 执行完成后触发",
        context_keys={"agent_type", "run_id", "output", "tokens_used", "cost_usd"},
        sync=False,
    ),
    "on_agent_error": HookDef(
        description="Agent 执行出错时触发",
        context_keys={"agent_type", "run_id", "error_message"},
        sync=False,
    ),
    "before_tool_call": HookDef(
        description="工具调用前触发",
        context_keys={"tool_name", "params"},
        sync=True,
    ),
}


def validate_hook_name(hook_name: str) -> None:
    """Raise ``ValueError`` if *hook_name* is not a known hook."""
    if hook_name not in HOOK_DEFINITIONS:
        known = ", ".join(HOOK_DEFINITIONS)
        raise ValueError(f"Unknown hook {hook_name!r}. Known hooks: {known}")
