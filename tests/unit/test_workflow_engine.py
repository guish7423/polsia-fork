"""Tests for WorkflowEngine — topological sort, node execution, full pipeline."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.orm.attributes import flag_modified

from app.models.workflow_definition import WorkflowDefinition, WorkflowRun
from app.services.workflow_engine import WorkflowEngine


# =============================================================================
# Topological Sort
# =============================================================================


class TestTopologicalSort:
    def test_valid_dag(self):
        """Simple linear DAG returns correct order."""
        nodes = [
            {"id": "A"},
            {"id": "B"},
            {"id": "C"},
        ]
        edges = [
            {"source": "A", "target": "B"},
            {"source": "B", "target": "C"},
        ]
        order = WorkflowEngine.topological_sort(nodes, edges)
        assert order == ["A", "B", "C"]

    def test_cycle_detection(self):
        """A cycle raises ValueError."""
        nodes = [
            {"id": "A"},
            {"id": "B"},
            {"id": "C"},
        ]
        edges = [
            {"source": "A", "target": "B"},
            {"source": "B", "target": "C"},
            {"source": "C", "target": "A"},
        ]
        with pytest.raises(ValueError, match="Cycle detected"):
            WorkflowEngine.topological_sort(nodes, edges)


# =============================================================================
# Node Execution Routing
# =============================================================================


class TestNodeExecutionRouting:
    """Verify _execute_node dispatches to the correct handler based on type."""

    @pytest.mark.asyncio
    async def test_routes_agent_node(self, mocker):
        """Agent-type node calls _execute_agent_node."""
        engine = WorkflowEngine()
        mock = mocker.patch.object(
            engine, "_execute_agent_node", return_value={"status": "success"}
        )
        node_data = {"id": "n1", "type": "agent", "agent_type": "test_agent"}
        result = await engine._execute_node("n1", node_data, None, 1)
        mock.assert_awaited_once_with("n1", node_data, None, 1)
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_routes_tool_node(self, mocker):
        """Tool-type node calls _execute_tool_node."""
        engine = WorkflowEngine()
        mock = mocker.patch.object(
            engine, "_execute_tool_node", return_value={"status": "success"}
        )
        node_data = {"id": "n2", "type": "tool", "tool_id": 42}
        result = await engine._execute_node("n2", node_data, None, 1)
        mock.assert_awaited_once_with("n2", node_data, None, 1)
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_routes_trigger_node(self, mocker):
        """Trigger-type node calls _execute_trigger_node."""
        engine = WorkflowEngine()
        mock = mocker.patch.object(
            engine, "_execute_trigger_node", return_value={"status": "success"}
        )
        node_data = {"id": "n3", "type": "trigger"}
        result = await engine._execute_node("n3", node_data, None, 1)
        mock.assert_awaited_once_with("n3", node_data, 1)
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_routes_output_node(self, mocker):
        """Output-type node calls _execute_output_node."""
        engine = WorkflowEngine()
        mock = mocker.patch.object(
            engine, "_execute_output_node", return_value={"status": "success"}
        )
        node_data = {"id": "n4", "type": "output"}
        result = await engine._execute_node("n4", node_data, None, 1)
        mock.assert_awaited_once_with("n4", node_data, 1)
        assert result["status"] == "success"


# =============================================================================
# get_upstream_outputs
# =============================================================================


class TestGetUpstreamOutputs:
    def test_single_upstream(self):
        """Single upstream node output is returned correctly."""
        edges = [{"source": "A", "target": "B"}]
        node_states = {
            "A": {"status": "completed", "output": {"price": 100}},
            "B": {"status": "pending", "output": None},
        }
        upstream = WorkflowEngine.get_upstream_outputs("B", edges, node_states)
        assert upstream == {"A": {"price": 100}}

    def test_multiple_upstreams(self):
        """Multiple upstream nodes are all collected."""
        edges = [
            {"source": "A", "target": "C"},
            {"source": "B", "target": "C"},
        ]
        node_states = {
            "A": {"status": "completed", "output": {"x": 1}},
            "B": {"status": "completed", "output": {"y": 2}},
            "C": {"status": "pending", "output": None},
        }
        upstream = WorkflowEngine.get_upstream_outputs("C", edges, node_states)
        assert upstream == {"A": {"x": 1}, "B": {"y": 2}}


# =============================================================================
# Full Pipeline Execution
# =============================================================================


class TestFullPipeline:
    """Integration-style tests with mocked WorkflowDefinition / WorkflowRun."""

    @pytest.mark.asyncio
    async def test_success_path(self, async_db_session, mocker):
        """Simple linear workflow completes with status='completed'."""
        # ── fixtures ──────────────────────────────────────────────────
        wf = WorkflowDefinition(
            tenant_id=1,
            name="Pipeline Test",
            nodes=[
                {"id": "n1", "type": "trigger"},
                {"id": "n2", "type": "agent", "agent_type": "test_agent"},
                {"id": "n3", "type": "output"},
            ],
            edges=[
                {"source": "n1", "target": "n2"},
                {"source": "n2", "target": "n3"},
            ],
        )
        async_db_session.add(wf)
        await async_db_session.flush()

        run = WorkflowRun(tenant_id=1, workflow_id=wf.id)
        async_db_session.add(run)
        await async_db_session.flush()

        engine = WorkflowEngine()

        # ── mock dispatch_agent ───────────────────────────────────────
        mock_dispatch = mocker.patch(
            "celery_app.tasks.agent_tasks.dispatch_agent",
            return_value={"result": "ok", "message": "mocked"},
        )

        # ── execute ───────────────────────────────────────────────────
        result = await engine.execute(wf, run, async_db_session, tenant_id=1)
        await async_db_session.refresh(run)

        # ── assert run status ─────────────────────────────────────────
        assert run.status == "completed"
        assert run.error is None
        assert run.started_at is not None
        assert run.completed_at is not None

        # ── assert node states ────────────────────────────────────────
        assert run.node_states is not None
        assert run.node_states["n1"]["status"] == "success"
        assert run.node_states["n2"]["status"] == "success"
        assert run.node_states["n3"]["status"] == "success"

        # ── assert dispatch_agent called ──────────────────────────────
        mock_dispatch.assert_called_once_with(
            "test_agent",
            context=mocker.ANY,
            task_id=None,
            tenant_id=1,
            function_calling=False,
        )
        call_context = mock_dispatch.call_args[1]["context"]
        assert call_context["agent_type"] == "test_agent"
        assert call_context["tenant_id"] == 1

        # ── assert result dict ────────────────────────────────────────
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_node_failure(self, async_db_session, mocker):
        """A failing agent node stops execution and marks the run as failed."""
        wf = WorkflowDefinition(
            tenant_id=1,
            name="Fail Pipeline",
            nodes=[
                {"id": "n1", "type": "trigger"},
                {"id": "n2", "type": "agent", "agent_type": "failing_agent"},
                {"id": "n3", "type": "output"},
            ],
            edges=[
                {"source": "n1", "target": "n2"},
                {"source": "n2", "target": "n3"},
            ],
        )
        async_db_session.add(wf)
        await async_db_session.flush()

        run = WorkflowRun(tenant_id=1, workflow_id=wf.id)
        async_db_session.add(run)
        await async_db_session.flush()

        engine = WorkflowEngine()

        # dispatch_agent raises
        mocker.patch(
            "celery_app.tasks.agent_tasks.dispatch_agent",
            side_effect=RuntimeError("Agent crashed"),
        )

        result = await engine.execute(wf, run, async_db_session, tenant_id=1)
        await async_db_session.refresh(run)

        assert run.status == "failed"
        assert run.error is not None
        assert "Agent crashed" in run.error

        # n1 should have succeeded, n2 should have failed
        assert run.node_states is not None
        assert run.node_states["n1"]["status"] == "success"
        assert run.node_states["n2"]["status"] == "error"
        # n3 should still be pending (never reached)
        assert run.node_states["n3"]["status"] == "pending"

        assert result["status"] == "failed"
