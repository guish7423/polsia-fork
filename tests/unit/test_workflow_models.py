"""Test WorkflowDefinition and WorkflowRun models."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.models.workflow_definition import WorkflowDefinition, WorkflowRun


@pytest.mark.asyncio
async def test_create_workflow_definition_with_json_fields(async_db_session):
    """Create a WorkflowDefinition with nodes/edges JSON."""
    wf = WorkflowDefinition(
        tenant_id=1,
        name="Test Workflow",
        nodes=[
            {"id": "node-1", "type": "trigger", "label": "Start"},
            {"id": "node-2", "type": "action", "label": "Process"},
        ],
        edges=[
            {"source": "node-1", "target": "node-2"},
        ],
    )
    async_db_session.add(wf)
    await async_db_session.flush()
    await async_db_session.refresh(wf)

    assert wf.id is not None
    assert wf.tenant_id == 1
    assert wf.name == "Test Workflow"
    assert len(wf.nodes) == 2
    assert wf.nodes[0]["id"] == "node-1"
    assert wf.nodes[1]["type"] == "action"
    assert len(wf.edges) == 1
    assert wf.edges[0]["source"] == "node-1"
    assert wf.created_at is not None
    assert wf.updated_at is not None


@pytest.mark.asyncio
async def test_workflow_definition_nullable_description(async_db_session):
    """description can be None."""
    wf = WorkflowDefinition(
        tenant_id=1,
        name="No Desc",
    )
    async_db_session.add(wf)
    await async_db_session.flush()

    assert wf.description is None


@pytest.mark.asyncio
async def test_create_workflow_run_with_pending_status(async_db_session):
    """Create a WorkflowRun with default pending status."""
    wf = WorkflowDefinition(
        tenant_id=1,
        name="WF for Run",
        nodes=[],
        edges=[],
    )
    async_db_session.add(wf)
    await async_db_session.flush()

    run = WorkflowRun(
        tenant_id=1,
        workflow_id=wf.id,
    )
    async_db_session.add(run)
    await async_db_session.flush()
    await async_db_session.refresh(run)

    assert run.id is not None
    assert run.workflow_id == wf.id
    assert run.status == "pending"
    assert run.node_states is None
    assert run.started_at is None
    assert run.completed_at is None
    assert run.error is None


@pytest.mark.asyncio
async def test_workflow_run_workflow_relationship(async_db_session):
    """WorkflowRun.workflow back-populates correctly."""
    wf = WorkflowDefinition(
        tenant_id=1,
        name="Related WF",
        nodes=[],
        edges=[],
    )
    async_db_session.add(wf)
    await async_db_session.flush()

    run = WorkflowRun(
        tenant_id=1,
        workflow_id=wf.id,
    )
    async_db_session.add(run)
    await async_db_session.flush()

    # Check relationship from Run → WorkflowDefinition
    assert run.workflow is not None
    assert run.workflow.name == "Related WF"

    # Check back-populates from WorkflowDefinition → runs
    # Use selectinload for async sessions to avoid greenlet issues
    q = select(WorkflowDefinition).where(
        WorkflowDefinition.id == wf.id
    ).options(selectinload(WorkflowDefinition.runs))
    result = await async_db_session.execute(q)
    wf_with_runs = result.scalar_one()
    assert len(wf_with_runs.runs) == 1
    assert wf_with_runs.runs[0].id == run.id


@pytest.mark.asyncio
async def test_update_workflow_run_node_states(async_db_session):
    """Update node_states JSON on an existing run."""
    wf = WorkflowDefinition(
        tenant_id=1,
        name="Node States WF",
        nodes=[],
        edges=[],
    )
    async_db_session.add(wf)
    await async_db_session.flush()

    run = WorkflowRun(
        tenant_id=1,
        workflow_id=wf.id,
    )
    async_db_session.add(run)
    await async_db_session.flush()

    # Update node_states
    run.node_states = {
        "node-1": "completed",
        "node-2": "running",
        "node-3": "pending",
    }
    await async_db_session.flush()
    await async_db_session.refresh(run)

    assert run.node_states is not None
    assert run.node_states["node-1"] == "completed"
    assert run.node_states["node-2"] == "running"
    assert run.node_states["node-3"] == "pending"

    # Partial update — flag_modified needed for in-place JSON mutation
    run.node_states["node-3"] = "failed"
    flag_modified(run, "node_states")
    await async_db_session.flush()
    await async_db_session.refresh(run)
    assert run.node_states["node-3"] == "failed"


@pytest.mark.asyncio
async def test_workflow_tenant_isolation(async_db_session):
    """Different tenant_id should isolate workflow definitions."""
    wf1 = WorkflowDefinition(
        tenant_id=1,
        name="Tenant 1 WF",
        nodes=[],
        edges=[],
    )
    wf2 = WorkflowDefinition(
        tenant_id=2,
        name="Tenant 2 WF",
        nodes=[],
        edges=[],
    )
    async_db_session.add_all([wf1, wf2])
    await async_db_session.flush()

    # Query tenant 1 only
    result = await async_db_session.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.tenant_id == 1)
    )
    tenant1_wfs = result.scalars().all()
    assert len(tenant1_wfs) == 1
    assert tenant1_wfs[0].name == "Tenant 1 WF"

    # Query tenant 2 only
    result = await async_db_session.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.tenant_id == 2)
    )
    tenant2_wfs = result.scalars().all()
    assert len(tenant2_wfs) == 1
    assert tenant2_wfs[0].name == "Tenant 2 WF"
