"""Test Workflow REST API endpoints — CRUD + Run + Status."""

import pytest

from app.models.workflow_definition import WorkflowDefinition


# ─── Shared Helpers ──────────────────────────────────────────────────────────


async def _create_workflow(client, headers, name="Test WF", nodes=None, edges=None):
    """Helper: create a workflow and return JSON response."""
    payload = {
        "name": name,
        "description": "Test description",
        "nodes": nodes or [{"id": "n1", "type": "trigger"}],
        "edges": edges or [],
    }
    resp = await client.post("/api/v1/workflows", json=payload, headers=headers)
    return resp


async def _create_workflow_and_return(client, headers, name="Test WF"):
    """Create a workflow and return the parsed JSON."""
    resp = await _create_workflow(client, headers, name=name)
    return resp.json()


# ─── CREATE ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_workflow(api_client, auth_headers):
    """POST /api/v1/workflows creates a new workflow definition."""
    resp = await _create_workflow(api_client, auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test WF"
    assert data["description"] == "Test description"
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["id"] == "n1"
    assert data["is_active"] is True
    assert data["id"] is not None
    assert data["created_at"] is not None


@pytest.mark.asyncio
async def test_create_workflow_defaults(api_client, auth_headers):
    """Defaults for description/nodes/edges should be empty."""
    resp = await api_client.post(
        "/api/v1/workflows",
        json={"name": "Minimal WF"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Minimal WF"
    assert data["description"] == ""
    assert data["nodes"] == []
    assert data["edges"] == []


# ─── LIST ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_workflows(api_client, auth_headers):
    """GET /api/v1/workflows returns paginated list."""
    await _create_workflow(api_client, auth_headers, name="WF 1")
    await _create_workflow(api_client, auth_headers, name="WF 2")

    resp = await api_client.get("/api/v1/workflows", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["workflows"]) == 2
    names = {w["name"] for w in data["workflows"]}
    assert names == {"WF 1", "WF 2"}


@pytest.mark.asyncio
async def test_list_workflows_pagination(api_client, auth_headers):
    """Pagination params limit and offset work correctly."""
    for i in range(5):
        await _create_workflow(api_client, auth_headers, name=f"WF {i}")

    # Page 1: limit=2
    resp = await api_client.get(
        "/api/v1/workflows?limit=2&offset=0", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["workflows"]) == 2

    # Page 2: offset=2
    resp = await api_client.get(
        "/api/v1/workflows?limit=2&offset=2", headers=auth_headers
    )
    assert resp.status_code == 200
    assert len(resp.json()["workflows"]) == 2


# ─── GET ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_workflow(api_client, auth_headers):
    """GET /api/v1/workflows/{id} returns the workflow by ID."""
    created = await _create_workflow_and_return(api_client, auth_headers)
    wf_id = created["id"]

    resp = await api_client.get(f"/api/v1/workflows/{wf_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == wf_id
    assert data["name"] == "Test WF"


@pytest.mark.asyncio
async def test_get_workflow_not_found(api_client, auth_headers):
    """GET a non-existent workflow returns 404."""
    resp = await api_client.get("/api/v1/workflows/99999", headers=auth_headers)
    assert resp.status_code == 404


# ─── UPDATE ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_workflow(api_client, auth_headers):
    """PUT /api/v1/workflows/{id} updates the workflow."""
    created = await _create_workflow_and_return(api_client, auth_headers)
    wf_id = created["id"]

    resp = await api_client.put(
        f"/api/v1/workflows/{wf_id}",
        json={"name": "Updated WF", "description": "New desc"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated WF"
    assert data["description"] == "New desc"


@pytest.mark.asyncio
async def test_update_workflow_nodes_edges(api_client, auth_headers):
    """PUT can update nodes and edges arrays."""
    created = await _create_workflow_and_return(api_client, auth_headers)
    wf_id = created["id"]

    new_nodes = [{"id": "x1", "type": "agent", "agent_type": "test"}]
    new_edges = [{"source": "x1", "target": "x2"}]
    resp = await api_client.put(
        f"/api/v1/workflows/{wf_id}",
        json={"nodes": new_nodes, "edges": new_edges},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["nodes"] == new_nodes
    assert data["edges"] == new_edges


@pytest.mark.asyncio
async def test_update_workflow_not_found(api_client, auth_headers):
    """PUT on non-existent workflow returns 404."""
    resp = await api_client.put(
        "/api/v1/workflows/99999",
        json={"name": "Nope"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ─── DELETE ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_workflow(api_client, auth_headers):
    """DELETE /api/v1/workflows/{id} deletes the workflow."""
    created = await _create_workflow_and_return(api_client, auth_headers)
    wf_id = created["id"]

    resp = await api_client.delete(f"/api/v1/workflows/{wf_id}", headers=auth_headers)
    assert resp.status_code == 204

    # Verify it's gone
    get_resp = await api_client.get(f"/api/v1/workflows/{wf_id}", headers=auth_headers)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_workflow_not_found(api_client, auth_headers):
    """DELETE on non-existent workflow returns 404."""
    resp = await api_client.delete("/api/v1/workflows/99999", headers=auth_headers)
    assert resp.status_code == 404


# ─── RUN WORKFLOW ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_workflow_success(api_client, auth_headers, mocker):
    """POST /api/v1/workflows/{id}/run creates a run and executes it."""
    async def _mock_execute(workflow, run, db, tenant_id):
        run.status = "completed"
        run.node_states = {"n1": {"status": "success", "output": None, "error": None,
                                   "started_at": None, "completed_at": None}}
        await db.flush()
        return {"status": "completed", "error": None, "node_states": run.node_states}

    mocker.patch(
        "app.services.workflow_engine.WorkflowEngine.execute",
        _mock_execute,
    )

    created = await _create_workflow_and_return(api_client, auth_headers)
    wf_id = created["id"]

    resp = await api_client.post(
        f"/api/v1/workflows/{wf_id}/run", headers=auth_headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["run_id"] is not None
    assert data["workflow_id"] == wf_id
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_run_workflow_not_found(api_client, auth_headers):
    """POST run on non-existent workflow returns 404."""
    resp = await api_client.post(
        "/api/v1/workflows/99999/run", headers=auth_headers
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_run_workflow_engine_error(api_client, auth_headers, mocker):
    """POST run handles engine errors gracefully."""
    from unittest.mock import AsyncMock
    mock_execute = AsyncMock(side_effect=RuntimeError("Engine crashed"))
    mocker.patch("app.services.workflow_engine.WorkflowEngine.execute", mock_execute)

    created = await _create_workflow_and_return(api_client, auth_headers)
    wf_id = created["id"]

    resp = await api_client.post(
        f"/api/v1/workflows/{wf_id}/run", headers=auth_headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "failed"
    assert "Engine crashed" in str(data.get("error", ""))


# ─── LIST RUNS ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_runs(api_client, auth_headers, mocker):
    """GET /api/v1/workflows/{id}/runs lists runs for a workflow."""
    async def _mock_execute(workflow, run, db, tenant_id):
        run.status = "completed"
        run.node_states = {}
        await db.flush()
        return {"status": "completed", "error": None, "node_states": {}}

    mocker.patch(
        "app.services.workflow_engine.WorkflowEngine.execute",
        _mock_execute,
    )

    created = await _create_workflow_and_return(api_client, auth_headers)
    wf_id = created["id"]

    # Run the workflow twice
    await api_client.post(f"/api/v1/workflows/{wf_id}/run", headers=auth_headers)
    await api_client.post(f"/api/v1/workflows/{wf_id}/run", headers=auth_headers)

    resp = await api_client.get(
        f"/api/v1/workflows/{wf_id}/runs", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["runs"]) == 2


@pytest.mark.asyncio
async def test_list_runs_empty(api_client, auth_headers):
    """GET runs for a workflow with no runs returns empty list."""
    created = await _create_workflow_and_return(api_client, auth_headers)
    wf_id = created["id"]

    resp = await api_client.get(
        f"/api/v1/workflows/{wf_id}/runs", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["runs"] == []


# ─── GET RUN STATUS ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_run_status(api_client, auth_headers, mocker):
    """GET /api/v1/workflows/runs/{run_id} returns run details."""
    async def _mock_execute(workflow, run, db, tenant_id):
        """Simulate engine execution that updates run status."""
        run.status = "completed"
        run.node_states = {"n1": {"status": "success"}}
        await db.flush()
        return {"status": "completed", "error": None, "node_states": run.node_states}

    mocker.patch(
        "app.services.workflow_engine.WorkflowEngine.execute",
        _mock_execute,
    )

    created = await _create_workflow_and_return(api_client, auth_headers)
    wf_id = created["id"]

    run_resp = await api_client.post(
        f"/api/v1/workflows/{wf_id}/run", headers=auth_headers
    )
    run_id = run_resp.json()["run_id"]

    resp = await api_client.get(
        f"/api/v1/workflows/runs/{run_id}", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == run_id
    assert data["workflow_id"] == wf_id
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_get_run_status_not_found(api_client, auth_headers):
    """GET non-existent run returns 404."""
    resp = await api_client.get(
        "/api/v1/workflows/runs/99999", headers=auth_headers
    )
    assert resp.status_code == 404
