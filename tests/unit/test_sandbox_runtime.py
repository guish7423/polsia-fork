"""Tests for Agent Sandbox Runtime — Docker container isolation.

Tests cover:
- Sandbox disabled → bypass container, run locally
- Blocked action (via sandbox_service.check_action) → blocked result
- Execution record created (SandboxExecution)
- Timeout → error result
- Image selection by agent type
- ContainerManager subprocess integration
"""

import pytest
from sqlalchemy import select
from unittest.mock import patch

from app.core.container_manager import ContainerResult
from app.models.sandbox_execution import SandboxExecution


# ─── Sandbox disabled → bypasses container ────────────────────────────────


@pytest.mark.asyncio
async def test_sandbox_disabled_bypasses_container(async_db_session):
    """When ``enabled=False``, no container call and no DB record."""
    from app.services.sandbox_runtime import SandboxRuntime

    runtime = SandboxRuntime(db=async_db_session, enabled=False)

    with patch("app.services.sandbox_service.check_action") as mock_check:
        mock_check.return_value = {"verdict": "allow", "rule_id": None, "message": "Disabled"}
        result = await runtime.execute_in_sandbox(
            agent_type="test_agent",
            command=["echo", "hello"],
        )

    assert result["status"] == "completed"
    assert result["sandbox_used"] is False

    # No SandboxExecution record created
    rows = (await async_db_session.execute(select(SandboxExecution))).scalars().all()
    assert len(rows) == 0


# ─── Blocked action ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sandbox_runtime_blocks_blocked_action(async_db_session):
    """When check_action returns block, container_manager must NOT be called."""
    from app.services.sandbox_runtime import SandboxRuntime
    from unittest.mock import patch

    runtime = SandboxRuntime(db=async_db_session, enabled=True)

    with patch("app.services.sandbox_service.check_action") as mock_check:
        mock_check.return_value = {
            "verdict": "block",
            "rule_id": "block_delete",
            "message": "Prevent any record deletion in sandbox mode",
        }
        result = await runtime.execute_in_sandbox(
            agent_type="test_agent",
            command=["rm", "-rf", "/"],
        )

    assert result["status"] == "blocked"
    assert "block_delete" in result.get("rule_id", "")


# ─── Execution record ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sandbox_records_execution(async_db_session):
    """Successful sandbox execution creates a SandboxExecution record."""
    from app.services.sandbox_runtime import SandboxRuntime
    from unittest.mock import patch

    runtime = SandboxRuntime(db=async_db_session, enabled=True)

    with (
        patch("app.services.sandbox_service.check_action") as mock_check,
        patch("app.services.sandbox_runtime.run_in_container") as mock_run,
    ):
        mock_check.return_value = {"verdict": "allow", "rule_id": None, "message": "Action allowed"}
        mock_run.return_value = ContainerResult(
            stdout="hello world", stderr="", exit_code=0, duration_ms=150, container_id="abc123",
        )

        result = await runtime.execute_in_sandbox(
            agent_type="code_agent",
            command=["python", "-c", "print('hello world')"],
        )

    assert result["status"] == "completed"
    assert result["sandbox_used"] is True
    assert result["stdout"] == "hello world"
    assert result["exit_code"] == 0

    rows = (await async_db_session.execute(select(SandboxExecution))).scalars().all()
    assert len(rows) == 1
    rec = rows[0]
    assert rec.agent_type == "code_agent"
    assert rec.status == "completed"
    assert rec.exit_code == 0
    assert rec.container_id == "abc123"


@pytest.mark.asyncio
async def test_sandbox_records_failed_execution(async_db_session):
    """Failed execution creates SandboxExecution with failed status."""
    from app.services.sandbox_runtime import SandboxRuntime
    from unittest.mock import patch

    runtime = SandboxRuntime(db=async_db_session, enabled=True)

    with (
        patch("app.services.sandbox_service.check_action") as mock_check,
        patch("app.services.sandbox_runtime.run_in_container") as mock_run,
    ):
        mock_check.return_value = {"verdict": "allow", "rule_id": None, "message": "Action allowed"}
        mock_run.return_value = ContainerResult(
            stdout="", stderr="Division by zero", exit_code=1, duration_ms=50,
        )

        result = await runtime.execute_in_sandbox(
            agent_type="code_agent",
            command=["python", "-c", "1/0"],
        )

    assert result["status"] == "failed"
    assert result["exit_code"] == 1

    rows = (await async_db_session.execute(select(SandboxExecution))).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "failed"
    assert rows[0].exit_code == 1


# ─── Timeout ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sandbox_timeout_returns_error(async_db_session):
    """When container execution times out, result shows timeout error."""
    from app.services.sandbox_runtime import SandboxRuntime
    from unittest.mock import patch

    runtime = SandboxRuntime(db=async_db_session, enabled=True)

    with (
        patch("app.services.sandbox_service.check_action") as mock_check,
        patch("app.services.sandbox_runtime.run_in_container") as mock_run,
    ):
        mock_check.return_value = {"verdict": "allow", "rule_id": None, "message": "Action allowed"}
        mock_run.return_value = ContainerResult(
            stdout="", stderr="Execution timed out after 300s", exit_code=-1, duration_ms=300_000,
        )

        result = await runtime.execute_in_sandbox(
            agent_type="code_agent",
            command=["python", "-c", "import time; time.sleep(400)"],
            timeout=300,
        )

    assert result["status"] == "timeout"
    assert result["exit_code"] == -1


# ─── Image selection ──────────────────────────────────────────────────────


def test_resolve_image_by_agent_type():
    """code → python:3.12-slim, shell → alpine:latest, other → default."""
    from app.services.sandbox_runtime import SandboxRuntime

    assert SandboxRuntime.resolve_image("code_agent") == "python:3.12-slim"
    assert SandboxRuntime.resolve_image("shell_agent") == "alpine:latest"
    assert SandboxRuntime.resolve_image("generic") == "python:3.12-slim"


# ─── ContainerManager subprocess test ─────────────────────────────────────


def test_container_manager_result_structure():
    """ContainerResult dataclass has expected fields."""
    from app.core.container_manager import ContainerResult

    r = ContainerResult(stdout="out", stderr="err", exit_code=0, duration_ms=100)
    assert r.stdout == "out"
    assert r.exit_code == 0


def test_container_manager_subprocess_fallback():
    """With docker SDK unavailable, falls back to subprocess."""
    from app.core.container_manager import run_in_container
    import subprocess
    from unittest.mock import patch, MagicMock

    mock_proc = MagicMock()
    mock_proc.stdout = b"hello from alpine"
    mock_proc.stderr = b""
    mock_proc.returncode = 0

    with patch("app.core.container_manager.subprocess.run", return_value=mock_proc):
        result = run_in_container(
            image="alpine:latest",
            command=["echo", "hello from alpine"],
            timeout=30,
        )

    assert result.stdout == "hello from alpine"
    assert result.exit_code == 0
    assert result.duration_ms >= 0


def test_container_manager_timeout():
    """Timeout returns exit_code -1 with timeout message."""
    from app.core.container_manager import run_in_container
    from unittest.mock import patch

    import subprocess as real_subprocess

    with patch("app.core.container_manager.subprocess.run",
               side_effect=real_subprocess.TimeoutExpired(cmd="docker", timeout=5)):
        result = run_in_container(
            image="python:3.12-slim",
            command=["sleep", "10"],
            timeout=5,
        )

    assert result.exit_code == -1
    assert "timed out" in result.stderr.lower()


def test_container_manager_container_id_in_result():
    """ContainerResult includes container_id when available."""
    from app.core.container_manager import ContainerResult

    r = ContainerResult(stdout="", stderr="", exit_code=0, duration_ms=0, container_id="abc")
    assert r.container_id == "abc"

    r2 = ContainerResult(stdout="", stderr="", exit_code=0, duration_ms=0)
    assert r2.container_id is None
