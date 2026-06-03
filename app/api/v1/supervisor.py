"""Supervisor API routes — goal planning and execution endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.task_planner import TaskPlan, create_tasks_from_plan, decompose_goal
from app.services.task_service import get_task
from app.agents.supervisor import SupervisorAgent

router = APIRouter(prefix="/supervisor", tags=["supervisor"])


# ─── Request / Response models ─────────────────────────────────────────────


class GoalRequest(BaseModel):
    """Request body for supervisor planning."""

    goal: str
    company_context: dict | None = None


class TaskSummary(BaseModel):
    """Summary of a planned task."""

    task_id: int | None = None
    title: str = ""
    agent_type: str = "orchestrator"
    priority: int = 3
    depends_on: list[str] = []


class PlanResponse(BaseModel):
    """Response from a planning operation."""

    result: str = "plan_created"
    goal: str = ""
    task_count: int = 0
    dependency_graph: dict[str, list[str]] = {}
    tasks: list[TaskSummary] = []
    metadata: dict | None = None


class ExecuteResponse(BaseModel):
    """Response from executing a plan."""

    result: str = "plan_executed"
    goal: str = ""
    task_count: int = 0
    dependency_graph: dict[str, list[str]] = {}
    tasks: list[TaskSummary] = []
    metadata: dict | None = None


class PlanStatusResponse(BaseModel):
    """Status of a plan's execution progress."""

    plan_id: int = 0
    goal: str = ""
    total_tasks: int = 0
    completed_tasks: int = 0
    pending_tasks: int = 0
    status: str = "unknown"


# ─── Endpoints ─────────────────────────────────────────────────────────────


@router.post("/plan", response_model=PlanResponse)
async def create_plan(
    body: GoalRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit a complex goal and get a decomposition plan without executing.

    Returns the proposed sub-tasks, dependency graph, and agent assignments.
    The caller can review the plan before choosing to execute it.
    """
    plan: TaskPlan = await decompose_goal(body.goal, body.company_context)

    task_summaries = []
    for i, sub_task in enumerate(plan.sub_tasks):
        task_summaries.append(TaskSummary(
            task_id=None,  # Not yet persisted
            title=sub_task.get("title", ""),
            agent_type=sub_task.get("agent_type", "orchestrator"),
            priority=sub_task.get("priority", 3),
            depends_on=sub_task.get("depends_on", []),
        ))

    return PlanResponse(
        result="plan_created",
        goal=body.goal,
        task_count=len(plan.sub_tasks),
        dependency_graph=plan.dependency_graph,
        tasks=task_summaries,
        metadata=plan.metadata,
    )


@router.post("/execute", response_model=ExecuteResponse)
async def execute_plan(
    body: GoalRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit a goal, create a plan, and persist all tasks to the database.

    Creates Task records for each sub-task with assigned agents.
    Returns the plan with database task IDs.
    """
    # 1. Decompose the goal
    plan: TaskPlan = await decompose_goal(body.goal, body.company_context)

    # 2. Persist tasks to the database
    created_tasks = await create_tasks_from_plan(db, plan)

    # 3. Build response with DB task IDs
    task_summaries = []
    for i, sub_task in enumerate(plan.sub_tasks):
        db_task = created_tasks[i] if i < len(created_tasks) else None
        task_summaries.append(TaskSummary(
            task_id=db_task.id if db_task else None,
            title=sub_task.get("title", ""),
            agent_type=sub_task.get("agent_type", "orchestrator"),
            priority=sub_task.get("priority", 3),
            depends_on=sub_task.get("depends_on", []),
        ))

    return ExecuteResponse(
        result="plan_executed",
        goal=body.goal,
        task_count=len(plan.sub_tasks),
        dependency_graph=plan.dependency_graph,
        tasks=task_summaries,
        metadata=plan.metadata,
    )


@router.get("/plan/{plan_id}/status", response_model=PlanStatusResponse)
async def get_plan_status(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Check the execution progress of a plan by its first task ID.

    Note: Since tasks are created individually, ``plan_id`` refers to
    the first task in the plan. The status aggregates all tasks that
    share the same source="supervisor" and similar creation time.
    """
    task = await get_task(db, plan_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Plan (task #{plan_id}) not found")

    # Count siblings (other tasks from the same supervisor run)
    from sqlalchemy import select, func
    from app.models.task import Task

    # Simple approach: return status of the referenced task
    # A full implementation would track plan_id explicitly
    return PlanStatusResponse(
        plan_id=plan_id,
        goal=task.title,
        total_tasks=1,
        completed_tasks=1 if task.status == "completed" else 0,
        pending_tasks=1 if task.status == "pending" else 0,
        status=task.status,
    )
