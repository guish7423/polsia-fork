"""Sandbox runtime — containerized agent execution with safety checks.

Provides :class:`SandboxRuntime` that runs agent commands inside Docker
containers after verifying against the existing sandbox safety rules.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.container_manager import ContainerResult, run_in_container


class SandboxRuntime:
    """Runs agent commands inside Docker containers with safety checks.

    Args:
        db: SQLAlchemy async session for persistence.
        enabled: When ``False``, bypasses container execution (``sandbox_used=False``).
    """

    DEFAULT_IMAGES: dict[str, str] = {
        "code": "python:3.12-slim",
        "shell": "alpine:latest",
    }
    DEFAULT_IMAGE: str = "python:3.12-slim"

    def __init__(self, db: Any, enabled: bool = True) -> None:
        self.db = db
        self.enabled = enabled

    # ── Image resolution ─────────────────────────────────────────────────

    @classmethod
    def resolve_image(cls, agent_type: str) -> str:
        """Pick a default image based on agent type hint."""
        lower = agent_type.lower()
        if "code" in lower:
            return cls.DEFAULT_IMAGES["code"]
        if "shell" in lower:
            return cls.DEFAULT_IMAGES["shell"]
        return cls.DEFAULT_IMAGE

    # ── Public API ───────────────────────────────────────────────────────

    async def execute_in_sandbox(
        self,
        agent_type: str,
        command: list[str],
        *,
        image: str | None = None,
        cpu_limit: str = "0.5",
        memory_limit_mb: int = 256,
        timeout: int = 300,
        agent_run_id: int | None = None,
    ) -> dict[str, Any]:
        """Execute *command* for *agent_type* inside a sandbox container.

        Steps:
        1. Check existing safety rules (``sandbox_service.check_action``).
        2. If sandbox is disabled, return immediately without container.
        3. Resolve image, run in container, persist :class:`SandboxExecution`.
        4. Return structured result dict.

        Returns:
            A dict with keys: ``status``, ``sandbox_used``, ``exit_code``,
            ``stdout``, ``stderr``, ``logs``, ``duration_ms``,
            ``container_id``, ``execution_id``.
        """
        # ── 1. Safety gate ───────────────────────────────────────────────
        import app.services.sandbox_service as sandbox_service

        verdict = sandbox_service.check_action(
            action_type="sandbox_execute",
            agent_type=agent_type,
        )

        if verdict["verdict"] == "block":
            return {
                "status": "blocked",
                "rule_id": verdict.get("rule_id"),
                "message": verdict.get("message", "Action blocked by sandbox"),
                "sandbox_used": False,
            }

        # ── 2. Bypass when disabled ──────────────────────────────────────
        if not self.enabled:
            return {
                "status": "completed",
                "sandbox_used": False,
                "message": "Sandbox disabled — bypassed container",
            }

        # ── 3. Run in container ──────────────────────────────────────────
        selected_image = image or self.resolve_image(agent_type)
        memory_limit = f"{memory_limit_mb}m"

        cr: ContainerResult = run_in_container(
            image=selected_image,
            command=command,
            cpu_limit=cpu_limit,
            memory_limit=memory_limit,
            timeout=timeout,
        )

        # ── 4. Determine status ──────────────────────────────────────────
        if cr.exit_code == -1:
            status = "timeout"
        elif cr.exit_code == 0:
            status = "completed"
        else:
            status = "failed"

        # ── 5. Persist record ────────────────────────────────────────────
        from app.models.sandbox_execution import SandboxExecution

        now = datetime.now(timezone.utc)
        record = SandboxExecution(
            agent_run_id=agent_run_id,
            agent_type=agent_type,
            container_id=cr.container_id,
            image=selected_image,
            status=status,
            cpu_limit=cpu_limit,
            memory_limit_mb=memory_limit_mb,
            command=" ".join(command) if isinstance(command, list) else command,
            exit_code=cr.exit_code,
            logs=_build_logs(cr),
            duration_ms=cr.duration_ms,
            started_at=now,
            finished_at=now,
        )
        self.db.add(record)
        await self.db.flush()

        return {
            "status": status,
            "sandbox_used": True,
            "exit_code": cr.exit_code,
            "stdout": cr.stdout,
            "stderr": cr.stderr,
            "logs": record.logs,
            "duration_ms": cr.duration_ms,
            "container_id": cr.container_id,
            "execution_id": record.id,
        }


def _build_logs(cr: ContainerResult) -> str:
    """Combine stdout + stderr into a single logs string."""
    parts: list[str] = []
    if cr.stdout:
        parts.append(f"STDOUT:\n{cr.stdout}")
    if cr.stderr:
        parts.append(f"STDERR:\n{cr.stderr}")
    return "\n\n".join(parts)
