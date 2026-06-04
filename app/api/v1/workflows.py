"""Workflow REST API — CRUD + Run + Status for Workflow Builder."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import get_db
from app.core.tenant_context import get_current_tenant
from app.models.workflow_definition import WorkflowDefinition, WorkflowRun

router = APIRouter(tags=["workflows"])


# ─── Pydantic Schemas ───────────────────────────────────────────────────────


class WorkflowCreate(BaseModel):
    name: str
    description: str = ""
    nodes: list[dict] = []
    edges: list[dict] = []


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    nodes: list[dict] | None = None
    edges: list[dict] | None = None


# ─── Tenant Helper ──────────────────────────────────────────────────────────


def _resolve_tenant_id() -> int:
    tenant = get_current_tenant()
    return tenant.id if tenant else 1  # fallback for backward compat


# ─── CRUD: Workflow Definitions ─────────────────────────────────────────────


@router.post("/workflows", status_code=201)
async def create_workflow(
    body: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new WorkflowDefinition."""
    tenant_id = _resolve_tenant_id()
    wf = WorkflowDefinition(
        tenant_id=tenant_id,
        name=body.name,
        description=body.description,
        nodes=body.nodes,
        edges=body.edges,
    )
    db.add(wf)
    await db.flush()
    await db.refresh(wf)
    return _workflow_to_dict(wf)


@router.get("/workflows")
async def list_workflows(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List all workflows for the current tenant (paginated)."""
    tenant_id = _resolve_tenant_id()

    # Total count
    count_q = select(func.count()).select_from(WorkflowDefinition).where(
        WorkflowDefinition.tenant_id == tenant_id,
        WorkflowDefinition.is_active == True,
    )
    total = (await db.execute(count_q)).scalar() or 0

    # Paginated query
    q = (
        select(WorkflowDefinition)
        .where(
            WorkflowDefinition.tenant_id == tenant_id,
            WorkflowDefinition.is_active == True,
        )
        .order_by(WorkflowDefinition.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.execute(q)).scalars().all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "workflows": [_workflow_to_dict(wf) for wf in rows],
    }


@router.get("/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single workflow by ID (with nodes/edges)."""
    tenant_id = _resolve_tenant_id()
    wf = await db.get(WorkflowDefinition, workflow_id)
    if not wf or wf.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _workflow_to_dict(wf)


@router.put("/workflows/{workflow_id}")
async def update_workflow(
    workflow_id: int,
    body: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update workflow name, description, nodes, or edges."""
    tenant_id = _resolve_tenant_id()
    wf = await db.get(WorkflowDefinition, workflow_id)
    if not wf or wf.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if body.name is not None:
        wf.name = body.name
    if body.description is not None:
        wf.description = body.description
    if body.nodes is not None:
        wf.nodes = body.nodes
        flag_modified(wf, "nodes")
    if body.edges is not None:
        wf.edges = body.edges
        flag_modified(wf, "edges")

    await db.flush()
    await db.refresh(wf)
    return _workflow_to_dict(wf)


@router.delete("/workflows/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a workflow (set is_active=False). Runs cascade via FK."""
    tenant_id = _resolve_tenant_id()
    wf = await db.get(WorkflowDefinition, workflow_id)
    if not wf or wf.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Soft delete — cascade deletes runs via relationship
    await db.delete(wf)
    await db.flush()
    return None


# ─── Workflow Run ────────────────────────────────────────────────────────────


@router.post("/workflows/{workflow_id}/run", status_code=201)
async def run_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Create a WorkflowRun and execute it via WorkflowEngine."""
    tenant_id = _resolve_tenant_id()
    wf = await db.get(WorkflowDefinition, workflow_id)
    if not wf or wf.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Create run record
    run = WorkflowRun(
        workflow_id=wf.id,
        tenant_id=tenant_id,
        status="pending",
        node_states={},
    )
    db.add(run)
    await db.flush()

    # Execute via engine
    from app.services.workflow_engine import WorkflowEngine

    try:
        result = await WorkflowEngine().execute(wf, run, db, tenant_id)
        await db.flush()
    except Exception as exc:
        run.status = "failed"
        run.error = str(exc)
        run.completed_at = datetime.now(timezone.utc)
        await db.flush()
        result = {"status": "failed", "error": str(exc), "node_states": run.node_states}

    return {
        "run_id": run.id,
        "workflow_id": wf.id,
        "status": run.status,
        "error": run.error,
        "node_states": run.node_states,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        **result,
    }


@router.get("/workflows/{workflow_id}/runs")
async def list_runs(
    workflow_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List runs for a specific workflow (paginated)."""
    tenant_id = _resolve_tenant_id()
    wf = await db.get(WorkflowDefinition, workflow_id)
    if not wf or wf.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Workflow not found")

    count_q = select(func.count()).select_from(WorkflowRun).where(
        WorkflowRun.workflow_id == workflow_id,
    )
    total = (await db.execute(count_q)).scalar() or 0

    q = (
        select(WorkflowRun)
        .where(WorkflowRun.workflow_id == workflow_id)
        .order_by(WorkflowRun.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.execute(q)).scalars().all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "runs": [_run_to_dict(r) for r in rows],
    }


@router.get("/workflows/runs/{run_id}")
async def get_run_status(
    run_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single run's status and node_states."""
    tenant_id = _resolve_tenant_id()
    run = await db.get(WorkflowRun, run_id)
    if not run or run.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Run not found")
    return _run_to_dict(run)


# ─── Serializers ─────────────────────────────────────────────────────────────


def _workflow_to_dict(wf: WorkflowDefinition) -> dict:
    return {
        "id": wf.id,
        "tenant_id": wf.tenant_id,
        "name": wf.name,
        "description": wf.description,
        "nodes": wf.nodes,
        "edges": wf.edges,
        "is_active": wf.is_active,
        "created_at": wf.created_at.isoformat() if wf.created_at else None,
        "updated_at": wf.updated_at.isoformat() if wf.updated_at else None,
    }


def _run_to_dict(run: WorkflowRun) -> dict:
    return {
        "id": run.id,
        "workflow_id": run.workflow_id,
        "tenant_id": run.tenant_id,
        "status": run.status,
        "node_states": run.node_states,
        "error": run.error,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }
