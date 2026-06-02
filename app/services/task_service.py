"""Task CRUD and agent type validation service."""

from datetime import date, datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.status_machine import TaskStatus, transition_status
from app.models.task import Task

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
]


def validate_agent_type(agent_type: str) -> bool:
    """Check if agent type is valid."""
    return agent_type in VALID_AGENT_TYPES


async def create_task(
    db: AsyncSession,
    title: str,
    agent_type: str,
    description: str | None = None,
    priority: int = 3,
    source: str = "orchestrator",
    status: str = "pending",
) -> Task:
    """Create a new task with validation."""
    # 确保初始状态合法
    _ = transition_status(TaskStatus.PENDING, TaskStatus(status))
    task = Task(
        title=title,
        description=description,
        agent_type=agent_type,
        priority=priority,
        status=status,
        source=source,
    )
    db.add(task)
    await db.flush()
    return task


async def get_tasks(
    db: AsyncSession,
    limit: int = 100,
    status: str | None = None,
    agent_type: str | None = None,
) -> list[Task]:
    """Get tasks with optional filters."""
    query = select(Task).order_by(Task.created_at.desc()).limit(limit)
    if status:
        query = query.where(Task.status == status)
    if agent_type:
        query = query.where(Task.agent_type == agent_type)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_task(db: AsyncSession, task_id: int) -> Task | None:
    """Get a single task by ID."""
    return await db.get(Task, task_id)


async def update_task_status(
    db: AsyncSession, task_id: int, status: str,
    result_summary: str | None = None, error_message: str | None = None,
) -> Task | None:
    """Update a task's status with state-machine validation.

    Raises ValueError if the transition is illegal.
    """
    task = await db.get(Task, task_id)
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


async def get_tasks_today(db: AsyncSession) -> int:
    """Count tasks created today for dashboard."""
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    query = select(func.count()).select_from(Task).where(
        Task.created_at >= today_start
    )
    result = await db.execute(query)
    return result.scalar() or 0


async def get_tasks_by_status(db: AsyncSession, status: str) -> int:
    """Count tasks with a given status."""
    query = select(func.count()).select_from(Task).where(Task.status == status)
    result = await db.execute(query)
    return result.scalar() or 0


async def get_paused_or_blocked_count(db: AsyncSession) -> dict[str, int]:
    """Count paused and blocked tasks for dashboard."""
    result = {"blocked": 0, "paused": 0, "in_review": 0}
    for status_key in result:
        query = select(func.count()).select_from(Task).where(
            Task.status == status_key
        )
        row = await db.execute(query)
        result[status_key] = row.scalar() or 0
    return result
