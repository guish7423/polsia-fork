"""Capability Registry — runtime agent capability lookup."""

from __future__ import annotations

from app.agents.registry import ensure_registered
from app.agents.schema import all_schemas, get_schema

# ─── Cache ──────────────────────────────────────────────────────────────────
_capability_index: dict[str, list[dict]] | None = None
"""capability → list of {agent_type, role, tier, tools} dicts."""


def _build_index() -> dict[str, list[dict]]:
    """Build a reverse index: capability → matching agents."""
    index: dict[str, list[dict]] = {}
    for schema_dict in all_schemas():
        agent_type = schema_dict["agent_type"]
        for cap in schema_dict.get("capabilities", []):
            index.setdefault(cap, []).append({
                "agent_type": agent_type,
                "role": schema_dict.get("role", ""),
                "tier": schema_dict.get("tier", "standard"),
                "tools": schema_dict.get("tools", []),
            })
    return index


def find_agents_by_capability(
    capability: str,
    min_tier: str | None = None,
) -> list[dict]:
    """Find agents that have a specific capability.

    Args:
        capability: The capability string to search (e.g. 'web_search').
        min_tier: Optional minimum tier filter ('core', 'standard', 'restricted').

    Returns:
        List of matching agent descriptors.
    """
    global _capability_index
    ensure_registered()
    if _capability_index is None:
        _capability_index = _build_index()

    matches = _capability_index.get(capability, [])
    if min_tier:
        tier_order = {"core": 0, "standard": 1, "restricted": 2, "sandboxed": 3}
        min_val = tier_order.get(min_tier, 0)
        matches = [
            m for m in matches
            if tier_order.get(m.get("tier", "standard"), 1) <= min_val
        ]
    return matches


def agent_capabilities(agent_type: str) -> list[str]:
    """Return a specific agent's capability list."""
    schema = get_schema(agent_type)
    if schema is None:
        return []
    return schema.capabilities


def all_capabilities() -> dict[str, list[str]]:
    """Return the complete capability map: capability → [agent_type, ...]."""
    global _capability_index
    ensure_registered()
    if _capability_index is None:
        _capability_index = _build_index()
    return {cap: [m["agent_type"] for m in matches]
            for cap, matches in _capability_index.items()}


def invalidate_capability_cache() -> None:
    """Force cache rebuild on next query (useful after schema changes)."""
    global _capability_index
    _capability_index = None
