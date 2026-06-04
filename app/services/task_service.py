"""Task CRUD and agent type validation service."""

from datetime import date, datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.status_machine import TaskStatus, transition_status
from app.models.task import Task
from app.models.tenant import Tenant

VALID_AGENT_TYPES = [
    "ads_management",
    "business_planning",
    "code_generation",
    "competitor_research",
    "customer_support",
    "deploy_agent",
    "deployment",
    "email_outreach",
    "evolution",
    "finance",
    "lead_nurturing",
    "market_intel",
    "monitor",
    "orchestrator",
    "order_fulfiller",
    "order_scanner",
    "social_media",
    "supervisor",
]


def validate_agent_type(agent_type: str) -> bool:
    """Check if agent type is valid."""
    return agent_type in VALID_AGENT_TYPES


def _fire_audit(tenant_id: int, entry_type: str, entry_id: str, action: str, payload: dict) -> None:
    """Fire-and-forget audit entry (background, never blocks)."""
    try:
        import asyncio
        from app.core.database import async_session
        from app.services.audit_chain import append_entry

        async def _log():
            async with async_session() as session:
                await append_entry(session, tenant_id, entry_type, entry_id, action, payload)
                await session.commit()

        asyncio.ensure_future(_log())
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Audit log failed (fire-and-forget)")


async def create_task(
    db: AsyncSession,
    title: str,
    agent_type: str,
    description: str | None = None,
    priority: int = 3,
    source: str = "orchestrator",
    status: str = "pending",
    tenant_id: int | None = None,
) -> Task:
    """Create a new task with validation and quota enforcement."""
    # 配额检查：当 tenant_id 提供时，检查任务月限额
    # tenant_id=0 表示 dev key（无 DB 行），跳过配额
    from app.config import settings

    if tenant_id and tenant_id > 0 and settings.quota_enabled:
        from app.services.quota_service import check_tasks_monthly_quota

        quota = await check_tasks_monthly_quota(db, tenant_id)
        if not quota.allowed:
            from fastapi import HTTPException
            raise HTTPException(status_code=429, detail="monthly_task_limit_exceeded")
    # 确保初始状态合法
    _ = transition_status(TaskStatus.PENDING, TaskStatus(status))
    task = Task(
        title=title,
        description=description,
        agent_type=agent_type,
        priority=priority,
        status=status,
        source=source,
        tenant_id=tenant_id,
    )
    db.add(task)
    await db.flush()

    # Fire-and-forget audit entry
    if tenant_id is not None:
        _fire_audit(tenant_id, "task_create", str(task.id), "created", {
            "agent_type": agent_type, "priority": priority, "source": source,
        })

    return task


async def get_tasks(
    db: AsyncSession,
    limit: int = 100,
    status: str | None = None,
    agent_type: str | None = None,
    tenant_id: int | None = None,
) -> list[Task]:
    """Get tasks with optional filters."""
    query = select(Task).order_by(Task.created_at.desc()).limit(limit)
    if status:
        query = query.where(Task.status == status)
    if agent_type:
        query = query.where(Task.agent_type == agent_type)
    if tenant_id is not None:
        query = query.where(Task.tenant_id == tenant_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_task(db: AsyncSession, task_id: int) -> Task | None:
    """Get a single task by ID."""
    return await db.get(Task, task_id)


async def update_task_status(
    db: AsyncSession, task_id: int, status: str,
    result_summary: str | None = None, error_message: str | None = None,
    tenant_id: int | None = None,
) -> Task | None:
    """Update a task's status with state-machine validation.

    Raises ValueError if the transition is illegal.
    """
    query = select(Task).where(Task.id == task_id)
    if tenant_id is not None:
        query = query.where(Task.tenant_id == tenant_id)
    result = await db.execute(query)
    task = result.scalar_one_or_none()
    if not task:
        return None
    # 状态机验证 (str → TaskStatus → 转换校验)
    current = TaskStatus(task.status) if task.status else TaskStatus.PENDING
    new = TaskStatus(status)
    validated = transition_status(current, new)
    task.status = validated.value
    if result_summary is not None:
        task.result_summary = result_summary
    if error_message is not None:
        task.error_message = error_message
    await db.flush()
    return task


async def create_tasks_batch(
    db: AsyncSession, tasks: list[dict],
) -> list[Task]:
    """Batch-create tasks from a list of task dicts.

    Each dict should contain: title (required), agent_type (defaults to
    ``"orchestrator"``), description, priority (default 3), source,
    metadata_json.
    """
    created = []
    for task_data in tasks:
        task = Task(
            title=task_data.get("title", "Unnamed task"),
            description=task_data.get("description"),
            agent_type=task_data.get("agent_type", "orchestrator"),
            priority=task_data.get("priority", 3),
            status="pending",
            source=task_data.get("source", "supervisor"),
            tenant_id=task_data.get("tenant_id"),
        )
        db.add(task)
        created.append(task)
    await db.flush()
    for task in created:
        await db.refresh(task)
    return created


async def get_tasks_today(db: AsyncSession, tenant_id: int | None = None) -> int:
    """Count tasks created today for dashboard."""
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    query = select(func.count()).select_from(Task).where(
        Task.created_at >= today_start
    )
    if tenant_id is not None:
        query = query.where(Task.tenant_id == tenant_id)
    result = await db.execute(query)
    return result.scalar() or 0


async def get_tasks_by_status(db: AsyncSession, status: str, tenant_id: int | None = None) -> int:
    """Count tasks with a given status."""
    query = select(func.count()).select_from(Task).where(Task.status == status)
    if tenant_id is not None:
        query = query.where(Task.tenant_id == tenant_id)
    result = await db.execute(query)
    return result.scalar() or 0


async def get_paused_or_blocked_count(db: AsyncSession, tenant_id: int | None = None) -> dict[str, int]:
    """Count paused and blocked tasks for dashboard."""
    result = {"blocked": 0, "paused": 0, "in_review": 0}
    for status_key in result:
        query = select(func.count()).select_from(Task).where(
            Task.status == status_key
        )
        if tenant_id is not None:
            query = query.where(Task.tenant_id == tenant_id)
        row = await db.execute(query)
        result[status_key] = row.scalar() or 0
    return result
