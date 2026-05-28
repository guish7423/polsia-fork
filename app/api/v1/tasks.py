"""Task API routes — CRUD for agent tasks."""
from typing import Optional

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_api_key
from app.core.database import get_db
from app.services.task_service import (
    VALID_AGENT_TYPES,
    create_task,
    get_tasks,
    get_task,
    update_task_status,
    validate_agent_type,
)

router = APIRouter(tags=["tasks"])


class CreateTaskRequest(BaseModel):
    title: str
    agent_type: str
    description: Optional[str] = None
    priority: int = 3


class UpdateTaskRequest(BaseModel):
    status: str
    result_summary: Optional[str] = None
    error_message: Optional[str] = None


@router.get("/tasks")
async def list_tasks(
    limit: int = Query(default=100, le=500),
    status: Optional[str] = None,
    agent_type: Optional[str] = None,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """List tasks with optional filters."""
    tasks = await get_tasks(db, limit=limit, status=status, agent_type=agent_type)
    return [
        {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "agent_type": t.agent_type,
            "priority": t.priority,
            "status": t.status,
            "source": t.source,
            "scheduled_date": t.scheduled_date.isoformat() if t.scheduled_date else None,
            "result_summary": t.result_summary,
            "error_message": t.error_message,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
        for t in tasks
    ]


@router.get("/tasks/{task_id}")
async def get_task_by_id(
    task_id: int,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Get a single task by ID."""
    task = await get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "agent_type": task.agent_type,
        "priority": task.priority,
        "status": task.status,
        "source": task.source,
        "result_summary": task.result_summary,
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


@router.post("/tasks", status_code=201)
async def create_new_task(
    body: CreateTaskRequest,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Create a new task."""
    if not validate_agent_type(body.agent_type):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid agent_type. Must be one of: {VALID_AGENT_TYPES}",
        )
    task = await create_task(db, body.title, body.agent_type, body.description, body.priority, "api")
    return {
        "id": task.id,
        "title": task.title,
        "agent_type": task.agent_type,
        "status": task.status,
    }


@router.put("/tasks/{task_id}")
async def update_task(
    task_id: int,
    body: UpdateTaskRequest,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Update task status and result."""
    task = await update_task_status(db, task_id, body.status, body.result_summary, body.error_message)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "id": task.id,
        "title": task.title,
        "status": task.status,
        "result_summary": task.result_summary,
    }
