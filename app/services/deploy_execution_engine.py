"""Deploy Execution Engine — materializes deliverable templates into real files.

Reads deliverables from ExternalOrder DB, writes to a staging directory,
creates git repo + .tar.gz archive, and tracks execution state.
"""

import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Execution state constants
STATE_PENDING = "pending"
STATE_RUNNING = "running"
STATE_COMPLETED = "completed"
STATE_FAILED = "failed"

# Base directory for all deployment projects
DEPLOY_BASE = os.path.expanduser("~/.crosswave/deploy-projects")

# Standard files to include in every deployment
ENV_EXAMPLE = """# Application Configuration
# Copy this file to .env and fill in your values
DEBUG=false
SECRET_KEY=change-me-to-a-random-string
DATABASE_URL=sqlite:///./data/app.db
"""

GITIGNORE = """__pycache__/
*.pyc
.env
*.db
data/
node_modules/
.next/
dist/
"""


def get_deploy_dir(order_id: int) -> str:
    """Get the staging directory path for an order."""
    return os.path.join(DEPLOY_BASE, f"order-{order_id}")


def get_archive_path(order_id: int) -> str:
    """Get the archive file path for an order."""
    return os.path.join(DEPLOY_BASE, f"order-{order_id}.tar.gz")


def get_log_path(order_id: int) -> str:
    """Get the execution log file path."""
    return os.path.join(DEPLOY_BASE, f"order-{order_id}.log")


def _log(order_id: int, message: str) -> None:
    """Append a timestamped log entry."""
    os.makedirs(DEPLOY_BASE, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with open(get_log_path(order_id), "a") as f:
        f.write(f"[{ts}] {message}\n")


def get_log(order_id: int) -> str:
    """Read the full execution log."""
    path = get_log_path(order_id)
    if os.path.exists(path):
        with open(path) as f:
            return f.read()
    return ""


def get_status(order_id: int) -> dict[str, Any]:
    """Get the current execution status for an order."""
    deploy_dir = get_deploy_dir(order_id)
    archive_path = get_archive_path(order_id)
    log = get_log(order_id)

    if not os.path.exists(deploy_dir) and not os.path.exists(archive_path):
        return {"state": STATE_PENDING, "log": "", "files": []}

    files = []
    if os.path.exists(deploy_dir):
        for root, dirs, filenames in os.walk(deploy_dir):
            for fname in filenames:
                fpath = os.path.join(root, fname)
                rel = os.path.relpath(fpath, deploy_dir)
                files.append({
                    "name": rel,
                    "size": os.path.getsize(fpath),
                    "path": fpath,
                })

    archive_size = None
    if os.path.exists(archive_path):
        archive_size = os.path.getsize(archive_path)

    # Determine state from log
    state = STATE_RUNNING if os.path.exists(deploy_dir) else STATE_PENDING
    if log and "ERROR" in log.split("\n")[-3:]:
        state = STATE_FAILED
    if archive_size is not None:
        state = STATE_COMPLETED

    return {
        "state": state,
        "deploy_dir": deploy_dir if os.path.exists(deploy_dir) else None,
        "archive_path": archive_path if os.path.exists(archive_path) else None,
        "archive_size": archive_size,
        "files": files,
        "file_count": len(files),
        "log": log,
    }


async def execute_deploy(
    order_id: int,
    deliverables: list[dict] | None = None,
    tier: str = "basic",
    project_title: str = "",
) -> dict[str, Any]:
    """Execute a deployment: write files, git init, create archive.

    This is designed to run synchronously (small operation — writing templates).
    For heavy lifting (docker compose up), use a Celery task wrapper.
    """
    deploy_dir = get_deploy_dir(order_id)
    archive_path = get_archive_path(order_id)
    slug = project_title.lower().replace(" ", "-").replace("--", "-")[:40] or f"project-{order_id}"

    # Clean any previous execution
    if os.path.exists(deploy_dir):
        shutil.rmtree(deploy_dir)

    _log(order_id, f"Starting deployment for order #{order_id}: {project_title}")
    _log(order_id, f"Target directory: {deploy_dir}")

    try:
        # ── 1. Create staging directory ──
        os.makedirs(deploy_dir, exist_ok=True)
        _log(order_id, f"Created staging directory: {deploy_dir}")

        # ── 2. Write standard files ──
        standard_files = {
            ".env.example": ENV_EXAMPLE,
            ".gitignore": GITIGNORE,
        }
        for fname, content in standard_files.items():
            fpath = os.path.join(deploy_dir, fname)
            with open(fpath, "w") as f:
                f.write(content)
            _log(order_id, f"  Created {fname} ({len(content)} bytes)")

        # ── 3. Write deliverable files ──
        written = set()
        for d in (deliverables or []):
            name = d.get("name", "")
            content = d.get("content", "")
            if not name or not content:
                continue
            # Handle subdirectory paths (e.g., .github/workflows/deploy.yml)
            fpath = os.path.join(deploy_dir, name)
            os.makedirs(os.path.dirname(fpath), exist_ok=True)
            byt = content.encode("utf-8")
            with open(fpath, "wb") as f:
                f.write(byt)
            written.add(name)
            _log(order_id, f"  Wrote {name} ({len(byt)} bytes)")

        _log(order_id, f"Written {len(written)} deliverable files")

        # ── 4. Create README if not already present ──
        if "README.md" not in written and project_title:
            readme = f"""# {project_title}

## Deployment Package
Auto-generated by CrossWave DeployEngine for order #{order_id}.

## Files
"""
            for name in sorted(written):
                readme += f"- `{name}`\n"
            readme += f"\n## Quick Start\n```bash\ncp .env.example .env\n# Edit .env\ndocker compose up -d\n```\n"
            readme_path = os.path.join(deploy_dir, "README.md")
            with open(readme_path, "w") as f:
                f.write(readme)
            _log(order_id, f"  Created README.md ({len(readme)} bytes)")

        # ── 5. Initialize git repo ──
        try:
            subprocess.run(
                ["git", "init"],
                cwd=deploy_dir,
                capture_output=True,
                timeout=10,
            )
            subprocess.run(
                ["git", "add", "-A"],
                cwd=deploy_dir,
                capture_output=True,
                timeout=30,
            )
            subprocess.run(
                ["git", "commit", "-m", f"Initial commit: {project_title} (order #{order_id})"],
                cwd=deploy_dir,
                capture_output=True,
                timeout=30,
                env={**os.environ, "GIT_AUTHOR_NAME": "CrossWave Deploy", "GIT_COMMITTER_NAME": "CrossWave Deploy",
                     "GIT_AUTHOR_EMAIL": "deploy@crosswave.app", "GIT_COMMITTER_EMAIL": "deploy@crosswave.app"},
            )
            _log(order_id, "Git repo initialized and committed")
        except subprocess.TimeoutExpired:
            _log(order_id, "  Git init timed out (non-critical, continuing)")
        except FileNotFoundError:
            _log(order_id, "  Git not available (non-critical, continuing)")
        except Exception as e:
            _log(order_id, f"  Git init warning: {e}")

        # ── 6. Create .tar.gz archive ──
        archive_path_tmp = archive_path + ".tmp"
        with tarfile.open(archive_path_tmp, "w:gz") as tar:
            tar.add(deploy_dir, arcname=slug)
        shutil.move(archive_path_tmp, archive_path)
        archive_size = os.path.getsize(archive_path)
        _log(order_id, f"Created archive: {archive_path} ({archive_size} bytes)")

        # ── 7. Summary ──
        _log(order_id, f"SUCCESS: Deployment package ready — {len(written)} files, {archive_size} bytes")
        return {
            "state": STATE_COMPLETED,
            "deploy_dir": deploy_dir,
            "archive_path": archive_path,
            "archive_size": archive_size,
            "files_written": len(written),
            "files": written,
        }

    except Exception as e:
        error_msg = f"ERROR: Deployment failed: {e}"
        _log(order_id, error_msg)
        return {
            "state": STATE_FAILED,
            "error": str(e),
            "deploy_dir": deploy_dir if os.path.exists(deploy_dir) else None,
        }
