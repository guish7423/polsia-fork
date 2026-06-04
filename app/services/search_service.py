"""Cross-model search service — unified search across tasks, agents, alerts, runs."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.models.agent_run import AgentRun
from app.models.activity_log import ActivityLog
from app.services.agent_monitor_service import AGENT_DESCRIPTIONS

SEARCHABLE_TYPES = ("tasks", "agents", "alerts", "runs")


def _compute_score(keyword: str, *fields: str) -> int:
    """Compute relevance score for a result.

    Scoring:
    - 4: exact match on any field (case-insensitive)
    - 3: keyword contained in a field value
    - 2: word-boundary match (keyword as a whole word)
    - 1: partial match (substring)

    Returns the highest score across all fields.
    """
    kw_lower = keyword.lower().strip()
    best = 0
    for field in fields:
        if not field:
            continue
        f_lower = field.lower()
        if f_lower == kw_lower:
            return 4  # Can't get higher than exact match
        if kw_lower in f_lower:
            # Whole word boundary check
            import re
            if re.search(rf"\b{re.escape(kw_lower)}\b", f_lower):
                best = max(best, 3)
            else:
                best = max(best, 2)
        # Partial character match for remaining
        # (already handled by "kw_lower in f_lower" above)
    return max(best, 1)  # At least 1 if we got here (it matched)


async def _search_tasks(
    db: AsyncSession, q: str, limit: int, tenant_id: int | None
) -> list[dict]:
    """Search tasks by title, description, and status."""
    pattern = f"%{q}%"
    query = (
        select(Task)
        .where(
            or_(
                Task.title.ilike(pattern),
                Task.description.ilike(pattern),
                Task.status.ilike(pattern),
            )
        )
        .order_by(Task.created_at.desc())
        .limit(limit)
    )
    if tenant_id is not None:
        query = query.where(Task.tenant_id == tenant_id)

    result = await db.execute(query)
    tasks = result.scalars().all()

    items = []
    for t in tasks:
        items.append(
            {
                "type": "task",
                "id": t.id,
                "title": t.title,
                "description": t.description or "",
                "url": f"/tasks/{t.id}",
                "score": _compute_score(q, t.title, t.description or "", t.status),
            }
        )
    return items


def _search_agents(q: str, limit: int) -> list[dict]:
    """Search agents by agent_type and description (in-memory)."""
    kw_lower = q.lower().strip()
    items = []
    for agent_type, description in AGENT_DESCRIPTIONS.items():
        if kw_lower in agent_type.lower() or kw_lower in description.lower():
            items.append(
                {
                    "type": "agent",
                    "id": agent_type,
                    "title": agent_type.replace("_", " ").title(),
                    "description": description,
                    "url": f"/agents/{agent_type}",
                    "score": _compute_score(q, agent_type, description),
                }
            )
    return items[:limit]


async def _search_alerts(
    db: AsyncSession, q: str, limit: int, tenant_id: int | None
) -> list[dict]:
    """Search alerts (activity logs) by summary/action."""
    pattern = f"%{q}%"
    query = (
        select(ActivityLog)
        .where(
            or_(
                ActivityLog.summary.ilike(pattern),
                ActivityLog.action.ilike(pattern),
            )
        )
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
    )
    # ActivityLog doesn't have tenant_id; search all
    result = await db.execute(query)
    logs = result.scalars().all()

    items = []
    for al in logs:
        items.append(
            {
                "type": "alert",
                "id": al.id,
                "title": al.action,
                "description": al.summary,
                "url": f"/activity/{al.id}",
                "score": _compute_score(q, al.summary, al.action),
            }
        )
    return items


async def _search_runs(
    db: AsyncSession, q: str, limit: int, tenant_id: int | None
) -> list[dict]:
    """Search agent runs by agent_type and status."""
    pattern = f"%{q}%"
    query = (
        select(AgentRun)
        .where(
            or_(
                AgentRun.agent_type.ilike(pattern),
                AgentRun.status.ilike(pattern),
            )
        )
        .order_by(AgentRun.started_at.desc())
        .limit(limit)
    )
    if tenant_id is not None:
        query = query.where(AgentRun.tenant_id == tenant_id)

    result = await db.execute(query)
    runs = result.scalars().all()

    items = []
    for r in runs:
        items.append(
            {
                "type": "run",
                "id": r.id,
                "title": f"{r.agent_type} run",
                "description": f"Status: {r.status}",
                "url": f"/agents/runs/{r.id}",
                "score": _compute_score(q, r.agent_type, r.status),
            }
        )
    return items


async def search_all(
    db: AsyncSession,
    q: str,
    types: list[str] | None = None,
    limit: int = 20,
    tenant_id: int | None = None,
) -> list[dict]:
    """Cross-model search returning unified results.

    Args:
        db: Database session.
        q: Search keyword.
        types: Entity types to search (default: all).
        limit: Max results.
        tenant_id: Tenant isolation filter.

    Returns:
        List of ``{type, id, title, description, url, score}`` sorted by
        relevance (exact match > fuzzy match > newer).
    """
    if not q or not q.strip():
        return []

    if types is None:
        types = list(SEARCHABLE_TYPES)

    results: list[dict] = []

    if "tasks" in types:
        results.extend(await _search_tasks(db, q, limit, tenant_id))
    if "agents" in types:
        results.extend(_search_agents(q, limit))
    if "alerts" in types:
        results.extend(await _search_alerts(db, q, limit, tenant_id))
    if "runs" in types:
        results.extend(await _search_runs(db, q, limit, tenant_id))

    # Sort: exact match (higher score) first, then newer (higher id for int IDs)
    def _sort_key(r: dict) -> tuple:
        id_val = r.get("id", 0)
        id_sort = -id_val if isinstance(id_val, (int, float)) else 0
        return (-r["score"], id_sort)

    results.sort(key=_sort_key)

    return results[:limit]
