"""Container manager — runs commands inside Docker containers with resource limits.

Uses ``docker-py`` SDK when available; falls back to ``subprocess docker run``.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field


@dataclass
class ContainerResult:
    """Result of a container execution."""

    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration_ms: int = 0
    container_id: str | None = None


# ─── Internal helpers (extracted for testability) ──────────────────────────


def _try_docker_sdk(
    image: str,
    command: list[str],
    cpu_limit: str,
    memory_limit: str,
    timeout: int,
) -> tuple[str, str, int, str | None]:
    """Execute via ``docker-py`` SDK.

    Raises ``ImportError`` if SDK is not installed.
    """
    import docker  # type: ignore[import-untyped]

    client = docker.from_env()
    container = client.containers.run(
        image=image,
        command=command,
        cpu_quota=int(float(cpu_limit) * 100_000),
        memory=memory_limit,
        detach=True,
        remove=True,
        stdout=True,
        stderr=True,
    )
    container.wait(timeout=timeout)
    stdout = container.logs(stdout=True, stderr=False).decode("utf-8")
    stderr = container.logs(stdout=False, stderr=True).decode("utf-8")
    exit_code: int = container.wait(timeout=5).get("StatusCode", -1)
    cid: str | None = container.id
    container.remove()
    return stdout, stderr, exit_code, cid


def _try_subprocess(
    image: str,
    command: list[str],
    cpu_limit: str,
    memory_limit: str,
    timeout: int,
) -> tuple[str, str, int, str | None]:
    """Fallback — execute via ``docker run`` subprocess."""
    cmd: list[str] = [
        "docker", "run", "--rm",
        f"--cpus={cpu_limit}",
        f"--memory={memory_limit}",
        image,
    ] + command
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    return (
        proc.stdout.decode("utf-8"),
        proc.stderr.decode("utf-8"),
        proc.returncode,
        None,  # no container_id from subprocess
    )


# ─── Public API ────────────────────────────────────────────────────────────


def run_in_container(
    image: str,
    command: list[str],
    cpu_limit: str = "0.5",
    memory_limit: str = "256m",
    timeout: int = 300,
) -> ContainerResult:
    """Run *command* inside a Docker container with resource limits.

    Args:
        image: Docker image to use (e.g. ``python:3.12-slim``).
        command: Command and arguments to run inside the container.
        cpu_limit: CPU limit (e.g. ``"0.5"`` = half a core).
        memory_limit: Memory limit (e.g. ``"256m"``).
        timeout: Max execution time in seconds (default 300).

    Returns:
        :class:`ContainerResult` with stdout, stderr, exit_code, duration_ms.
    """
    start = time.monotonic()

    try:
        try:
            stdout, stderr, exit_code, cid = _try_docker_sdk(
                image, command, cpu_limit, memory_limit, timeout,
            )
        except (ImportError, OSError, Exception) as _sdk_err:
            # Fall through to subprocess when docker SDK is unavailable
            # (ImportError = SDK not installed, OSError/DockerException = daemon not running)
            stdout, stderr, exit_code, cid = _try_subprocess(
                image, command, cpu_limit, memory_limit, timeout,
            )

        duration = int((time.monotonic() - start) * 1000)
        return ContainerResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            duration_ms=duration,
            container_id=cid,
        )

    except subprocess.TimeoutExpired:
        duration = int((time.monotonic() - start) * 1000)
        return ContainerResult(
            stderr=f"Execution timed out after {timeout}s",
            exit_code=-1,
            duration_ms=duration,
        )

    except Exception as exc:
        duration = int((time.monotonic() - start) * 1000)
        return ContainerResult(
            stderr=f"Container error: {exc}",
            exit_code=-2,
            duration_ms=duration,
        )
