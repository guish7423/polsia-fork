"""WorkflowEngine — Sequential DAG executor.

Executes workflow nodes in topological order, routing each node to the
appropriate handler (agent / tool / trigger / output).
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.workflow_definition import WorkflowDefinition, WorkflowRun

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Sequential DAG executor.  Executes nodes in topological order,
    one at a time.
    """

    # ── Topological Sort ─────────────────────────────────────────────────

    @staticmethod
    def topological_sort(nodes: list[dict], edges: list[dict]) -> list[str]:
        """Kahn's algorithm.  Returns node IDs in execution order.

        Raises:
            ValueError: When a cycle is detected in the graph.
        """
        # Build adjacency list and in-degree map
        adj: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = {}

        for node in nodes:
            nid = node["id"]
            in_degree.setdefault(nid, 0)

        for edge in edges:
            src = edge["source"]
            tgt = edge["target"]
            adj[src].append(tgt)
            in_degree[tgt] = in_degree.get(tgt, 0) + 1

        # Collect zero-in-degree nodes
        queue: deque[str] = deque()
        for nid, deg in in_degree.items():
            if deg == 0:
                queue.append(nid)

        order: list[str] = []
        while queue:
            nid = queue.popleft()
            order.append(nid)
            for neighbour in adj[nid]:
                in_degree[neighbour] -= 1
                if in_degree[neighbour] == 0:
                    queue.append(neighbour)

        if len(order) != len(in_degree):
            raise ValueError("Cycle detected in workflow DAG")

        return order

    # ── Main Execution Loop ──────────────────────────────────────────────

    async def execute(
        self,
        workflow: WorkflowDefinition,
        run: WorkflowRun,
        db: AsyncSession,
        tenant_id: int,
    ) -> dict:
        """Main execution loop.

        1. Sort nodes topologically.
        2. For each node, determine type and execute.
        3. Store result in ``run.node_states``.
        4. Update ``run.status`` on completion or error.
        """
        nodes: list[dict] = workflow.nodes
        edges: list[dict] = workflow.edges

        node_order = self.topological_sort(nodes, edges)

        # Initialise node_states
        now = datetime.now(timezone.utc)
        run.status = "running"
        run.started_at = now
        states: dict[str, dict] = {
            nid: {"status": "pending", "output": None, "error": None,
                  "started_at": None, "completed_at": None}
            for nid in node_order
        }
        run.node_states = states
        await db.flush()

        overall_error: str | None = None

        for node_id in node_order:
            # Find node data from workflow definition
            node_data: dict | None = next(
                (n for n in nodes if n["id"] == node_id), None
            )
            if node_data is None:
                error_msg = f"Node '{node_id}' not found in workflow definition"
                states[node_id] = {
                    "status": "error",
                    "output": None,
                    "error": error_msg,
                    "started_at": None,
                    "completed_at": None,
                }
                overall_error = error_msg
                break

            # Mark as running
            node_start = datetime.now(timezone.utc)
            states[node_id]["started_at"] = node_start.isoformat()
            await db.flush()

            try:
                result = await self._execute_node(
                    node_id, node_data, db, tenant_id,
                )
                states[node_id]["status"] = result["status"]
                states[node_id]["output"] = result.get("output")
                if result["status"] == "error":
                    error_detail = result.get("error", "Unknown error")
                    states[node_id]["error"] = error_detail
                    overall_error = error_detail
                    run.node_states = states
                    flag_modified(run, "node_states")
                    await db.flush()
                    break
            except Exception as exc:
                states[node_id]["status"] = "error"
                states[node_id]["error"] = str(exc)
                overall_error = str(exc)
                run.node_states = states
                flag_modified(run, "node_states")
                await db.flush()
                break
            finally:
                states[node_id]["completed_at"] = (
                    datetime.now(timezone.utc).isoformat()
                )
                run.node_states = states
                flag_modified(run, "node_states")
                await db.flush()

        # Finalise run
        completed_at = datetime.now(timezone.utc)
        run.completed_at = completed_at
        run.node_states = states
        if overall_error:
            run.status = "failed"
            run.error = overall_error
        else:
            run.status = "completed"
        flag_modified(run, "node_states")
        await db.flush()

        return {
            "status": run.status,
            "error": run.error,
            "node_states": run.node_states,
        }

    # ── Node Routing ─────────────────────────────────────────────────────

    async def _execute_node(
        self,
        node_id: str,
        node_data: dict,
        db: AsyncSession,
        tenant_id: int,
    ) -> dict:
        """Route to the appropriate handler based on node type."""
        node_type = node_data.get("type", "").lower()

        if node_type == "agent":
            return await self._execute_agent_node(node_id, node_data, db, tenant_id)
        elif node_type == "tool":
            return await self._execute_tool_node(node_id, node_data, db, tenant_id)
        elif node_type == "trigger":
            return await self._execute_trigger_node(node_id, node_data, tenant_id)
        elif node_type == "output":
            return await self._execute_output_node(node_id, node_data, tenant_id)
        else:
            return {
                "status": "error",
                "output": None,
                "error": f"Unknown node type: {node_type}",
            }

    # ── Agent Node ───────────────────────────────────────────────────────

    async def _execute_agent_node(
        self,
        node_id: str,
        node_data: dict,
        db: AsyncSession,
        tenant_id: int,
    ) -> dict:
        """Execute an agent node by calling ``dispatch_agent``.

        ``dispatch_agent`` is synchronous — always wrap with
        ``asyncio.to_thread()``.
        """
        # Lazy import to avoid circular imports
        from celery_app.tasks.agent_tasks import dispatch_agent

        agent_type: str = node_data.get("agent_type", "")
        if not agent_type:
            return {
                "status": "error",
                "output": None,
                "error": f"Agent node '{node_id}' missing 'agent_type'",
            }

        # Build context from upstream outputs
        upstream = self.get_upstream_outputs(node_id, [], {})
        context: dict[str, Any] = {
            "agent_type": agent_type,
            "node_id": node_id,
            "tenant_id": tenant_id,
            "upstream": upstream,
        }
        config = node_data.get("config", {})
        if config:
            context["config"] = config

        try:
            result = await asyncio.to_thread(
                dispatch_agent,
                agent_type,
                context=context,
                task_id=None,
                tenant_id=tenant_id,
                function_calling=False,
            )
            return {"status": "success", "output": result}
        except Exception as exc:
            logger.exception("Agent node '%s' failed", node_id)
            return {"status": "error", "output": None, "error": str(exc)}

    # ── Tool Node ────────────────────────────────────────────────────────

    async def _execute_tool_node(
        self,
        node_id: str,
        node_data: dict,
        db: AsyncSession,
        tenant_id: int,
    ) -> dict:
        """Execute an MCP tool node.

        ``execute_tool`` is async — call directly with ``await``.
        """
        # Lazy import to avoid circular imports
        from app.services.mcp_gateway import execute_tool

        tool_id: int | None = node_data.get("tool_id")
        if tool_id is None:
            return {
                "status": "error",
                "output": None,
                "error": f"Tool node '{node_id}' missing 'tool_id'",
            }

        params = dict(node_data.get("params", {}))

        try:
            result = await execute_tool(
                db,
                tool_id=tool_id,
                params=params,
                agent_run_id=None,
                tenant_id=tenant_id,
            )
            return {"status": "success", "output": result}
        except Exception as exc:
            logger.exception("Tool node '%s' (tool_id=%d) failed", node_id, tool_id)
            return {"status": "error", "output": None, "error": str(exc)}

    # ── Trigger Node ─────────────────────────────────────────────────────

    async def _execute_trigger_node(
        self,
        node_id: str,
        node_data: dict,
        tenant_id: int,
    ) -> dict:
        """Trigger nodes just pass through — return input as output."""
        return {
            "status": "success",
            "output": {
                "node_id": node_id,
                "type": "trigger",
                "tenant_id": tenant_id,
            },
        }

    # ── Output Node ─────────────────────────────────────────────────────

    async def _execute_output_node(
        self,
        node_id: str,
        node_data: dict,
        tenant_id: int,
    ) -> dict:
        """Output nodes accumulate final results — return merged output."""
        return {
            "status": "success",
            "output": {
                "node_id": node_id,
                "type": "output",
                "tenant_id": tenant_id,
            },
        }

    # ── Upstream Outputs ─────────────────────────────────────────────────

    @staticmethod
    def get_upstream_outputs(
        node_id: str,
        edges: list[dict],
        node_states: dict[str, dict],
    ) -> dict[str, Any]:
        """Collect outputs from all upstream nodes connected to *node_id*.

        Returns ``{upstream_node_id: output}`` for context injection.
        """
        upstream_ids = [
            edge["source"] for edge in edges if edge["target"] == node_id
        ]
        return {
            uid: node_states.get(uid, {}).get("output")
            for uid in upstream_ids
        }
