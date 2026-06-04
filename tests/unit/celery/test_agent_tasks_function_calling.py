"""Tests for function_calling parameter in Celery agent task dispatch.

Tests that the ``function_calling`` flag is correctly wired from
``run_agent()`` (and ``dispatch_agent()``) to the agent instance
before ``agent.run()`` is called.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_agent_run_deps():
    """Set up all mocks needed to exercise run_agent() standard path.

    All heavy dependencies (DB, Celery, sandbox, events) are mocked.
    Returns the mock agent instance so callers can inspect its state.
    """
    patchers = [
        # All dependencies are lazy-imported inside run_agent(),
        # so we patch at the source module where they're defined.
        patch("app.agents.agent_map"),
        patch("app.agents.base.sandbox_verdict", return_value={"verdict": "allow"}),
        patch("app.core.database.async_session"),
        patch("app.models.agent_run.AgentRun"),
        patch("app.models.task.Task"),
        patch("app.core.events.publish_activity"),
        patch("app.services.plugin_registry.call_hooks"),
        patch("app.config.settings"),
        patch("app.services.sandbox_runtime.SandboxRuntime"),
    ]

    mocks = [p.start() for p in patchers]
    try:
        (
            mock_map,
            mock_verdict,
            mock_sesh_factory,
            mock_agent_run_cls,
            mock_task_model,
            mock_publish,
            mock_hooks,
            mock_settings,
            mock_sandbox_runtime,
        ) = mocks

        mock_settings.durable_execution_enabled = False
        mock_settings.scheduler_enabled = False
        mock_settings.sandbox_enabled = False

        # Mock agent
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value={"result": "ok"})
        mock_cls = MagicMock(return_value=mock_agent)
        mock_map.get.return_value = mock_cls

        # Mock DB
        mock_session = AsyncMock()
        mock_sesh_factory.return_value.__aenter__.return_value = mock_session
        mock_session.get = AsyncMock(return_value=None)

        # Mock AgentRun model instance
        mock_run_inst = MagicMock()
        mock_run_inst.id = 1
        mock_agent_run_cls.return_value = mock_run_inst

        yield mock_agent
    finally:
        for p in patchers:
            p.stop()


def _call_run_agent(agent_type, **kwargs):
    """Helper to call run_agent via its .run() method, bypassing
    Celery decorator machinery.

    ``bind=True`` means ``.run()`` does NOT expect a ``self`` argument
    — Celery injects it internally.
    """
    from celery_app.tasks.agent_tasks import run_agent
    return run_agent.run(agent_type, **kwargs)


@pytest.fixture
def mock_durable_deps():
    """Set up mocks for the durable execution path."""
    patchers = [
        patch("app.agents.agent_map"),
        patch("app.core.database.async_session"),
        patch("app.core.checkpoint.Checkpoint"),
        patch("app.models.agent_run.AgentRun"),
        patch("app.models.task.Task"),
        patch("app.core.events.publish_activity"),
        patch("app.services.plugin_registry.call_hooks"),
        patch("app.config.settings"),
    ]

    mocks = [p.start() for p in patchers]
    try:
        (
            mock_map,
            mock_sesh_factory,
            mock_cp_cls,
            mock_agent_run_cls,
            mock_task_model,
            mock_publish,
            mock_hooks,
            mock_settings,
        ) = mocks

        mock_settings.durable_execution_enabled = True

        # Mock agent
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value={"result": "ok"})
        mock_map.get.return_value = MagicMock(return_value=mock_agent)

        # Mock DB
        mock_session = AsyncMock()
        mock_sesh_factory.return_value.__aenter__.return_value = mock_session
        mock_session.get = AsyncMock(return_value=None)

        # Mock Checkpoint
        mock_cp_inst = MagicMock()
        mock_cp_inst.run = AsyncMock(
            side_effect=lambda step, fn, *a, **kw: fn(*a, **kw)
            if step == "execute"
            else None
        )
        mock_cp_inst.save_to_db = AsyncMock()
        mock_cp_cls.return_value = mock_cp_inst

        # Mock AgentRun
        mock_run_inst = MagicMock()
        mock_run_inst.id = 2
        mock_agent_run_cls.return_value = mock_run_inst

        yield mock_agent
    finally:
        for p in patchers:
            p.stop()


# ── Tests: dispatch_agent ─────────────────────────────────────────────────────


class TestDispatchAgentFunctionCalling:
    """dispatch_agent() passes function_calling through to run_agent()."""

    def test_dispatch_agent_passes_function_calling_true(self):
        """function_calling=True is forwarded to run_agent."""
        from celery_app.tasks.agent_tasks import dispatch_agent

        with patch("celery_app.tasks.agent_tasks.run_agent") as mock_run:
            mock_run.return_value = {"result": "ok"}
            dispatch_agent("test_agent", function_calling=True)

        assert mock_run.call_count == 1
        kwargs = mock_run.call_args[1]
        assert kwargs.get("function_calling") is True

    def test_dispatch_agent_defaults_function_calling_false(self):
        """Default call without function_calling defaults to False."""
        from celery_app.tasks.agent_tasks import dispatch_agent

        with patch("celery_app.tasks.agent_tasks.run_agent") as mock_run:
            mock_run.return_value = {"result": "ok"}
            dispatch_agent("test_agent")

        assert mock_run.call_count == 1
        kwargs = mock_run.call_args[1]
        assert kwargs.get("function_calling") is False

    def test_dispatch_agent_passes_context_and_task_id(self):
        """Other existing params still pass through correctly."""
        from celery_app.tasks.agent_tasks import dispatch_agent

        with patch("celery_app.tasks.agent_tasks.run_agent") as mock_run:
            mock_run.return_value = {"result": "ok"}
            dispatch_agent(
                "test_agent",
                context={"key": "val"},
                task_id=42,
                tenant_id=7,
            )

        kwargs = mock_run.call_args[1]
        assert kwargs.get("context") == {"key": "val"}
        assert kwargs.get("task_id") == 42
        assert kwargs.get("function_calling") is False


# ── Tests: run_agent flag propagation ─────────────────────────────────────────


class TestRunAgentFunctionCallingFlag:
    """Agent instance gets _function_calling_enabled set before run()."""

    @staticmethod
    def _make_task():
        t = MagicMock()
        t.request.retries = 0
        return t

    def test_function_calling_true_sets_flag(self, mock_agent_run_deps):
        """function_calling=True → agent._function_calling_enabled is True."""
        _call_run_agent(
            "test_agent",
            context={"input": "test"},
            function_calling=True,
        )

        agent = mock_agent_run_deps
        assert agent._function_calling_enabled is True

    def test_function_calling_false_sets_flag(self, mock_agent_run_deps):
        """function_calling=False → agent._function_calling_enabled is False."""
        _call_run_agent(
            "test_agent",
            context={},
            function_calling=False,
        )

        agent = mock_agent_run_deps
        assert agent._function_calling_enabled is False

    def test_backward_compatible_default(self, mock_agent_run_deps):
        """Default (no function_calling arg) → _function_calling_enabled=False."""
        _call_run_agent("test_agent", context={})

        agent = mock_agent_run_deps
        assert agent._function_calling_enabled is False


# ── Tests: durable path ───────────────────────────────────────────────────────


class TestRunAgentDurablePathFunctionCalling:
    """function_calling flag propagates in the durable execution path too."""

    def test_durable_path_sets_flag(self, mock_durable_deps):
        """When durable_execution_enabled, flag is set on agent."""
        _call_run_agent(
            "test_agent",
            context={},
            function_calling=True,
        )

        agent = mock_durable_deps
        assert agent._function_calling_enabled is True

    def test_durable_path_false_default(self, mock_durable_deps):
        """Durable path with function_calling=False also works."""
        _call_run_agent(
            "test_agent",
            context={},
            function_calling=False,
        )

        agent = mock_durable_deps
        assert agent._function_calling_enabled is False
