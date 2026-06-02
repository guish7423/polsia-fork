"""HITL Interrupt Queue — Human-in-the-Loop for agent actions.

Pattern: Agent encounters a decision that needs approval → creates interrupt
→ task PAUSES → HQ displays pending → human Approves/Rejects → agent resumes.

Builds on Phase 0 (TaskStatus.PAUSED/BLOCKED) and Phase 1b (checkpoint).
"""

import json
import os
import time
from typing import Any

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
INTERRUPTS_FILE = os.path.join(DATA_DIR, "interrupts.json")


class InterruptStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _load() -> dict[str, Any]:
    try:
        with open(INTERRUPTS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"next_id": 1, "interrupts": []}


def _save(data: dict[str, Any]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(INTERRUPTS_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def create_interrupt(
    agent_type: str,
    task_id: int,
    reason: str,
    context: dict[str, Any] | None = None,
) -> int:
    """Create a pending interrupt. Returns the interrupt ID."""
    data = _load()
    iid = data["next_id"]
    data["next_id"] = iid + 1
    data["interrupts"].append({
        "id": iid,
        "agent_type": agent_type,
        "task_id": task_id,
        "reason": reason,
        "context": context or {},
        "status": InterruptStatus.PENDING,
        "created_at": time.time(),
        "updated_at": None,
        "decision": None,
        "decision_note": None,
    })
    _save(data)
    return iid


def approve_interrupt(interrupt_id: int) -> dict[str, Any] | None:
    """Approve a pending interrupt. Returns the context dict for the agent."""
    data = _load()
    for i in data["interrupts"]:
        if i["id"] == interrupt_id and i["status"] == InterruptStatus.PENDING:
            i["status"] = InterruptStatus.APPROVED
            i["updated_at"] = time.time()
            i["decision"] = "approved"
            _save(data)
            return i["context"]
    return None


def reject_interrupt(interrupt_id: int, reason: str) -> bool:
    """Reject a pending interrupt with a reason."""
    data = _load()
    for i in data["interrupts"]:
        if i["id"] == interrupt_id and i["status"] == InterruptStatus.PENDING:
            i["status"] = InterruptStatus.REJECTED
            i["updated_at"] = time.time()
            i["decision"] = "rejected"
            i["decision_note"] = reason
            _save(data)
            return True
    return False


def get_pending_interrupts(agent_type: str | None = None) -> list[dict[str, Any]]:
    """Return all pending interrupts, optionally filtered by agent type."""
    data = _load()
    return [
        i for i in data["interrupts"]
        if i["status"] == InterruptStatus.PENDING
        and (agent_type is None or i["agent_type"] == agent_type)
    ]


def has_pending_interrupt(agent_type: str, task_id: int | None = None) -> bool:
    """Check if an agent has a pending interrupt (optionally for a specific task)."""
    data = _load()
    for i in data["interrupts"]:
        if i["status"] != InterruptStatus.PENDING:
            continue
        if i["agent_type"] != agent_type:
            continue
        if task_id is not None and i["task_id"] != task_id:
            continue
        return True
    return False


def get_pending_count() -> int:
    """Fast count of all pending interrupts."""
    return len(get_pending_interrupts())


def get_interrupt(interrupt_id: int) -> dict[str, Any] | None:
    """Get a single interrupt by ID."""
    data = _load()
    for i in data["interrupts"]:
        if i["id"] == interrupt_id:
            return i
    return None


def list_all(
    status: str | None = None,
    agent_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List interrupts with optional filters, newest first."""
    data = _load()
    results = data["interrupts"]
    if status:
        results = [i for i in results if i["status"] == status]
    if agent_type:
        results = [i for i in results if i["agent_type"] == agent_type]
    results.sort(key=lambda x: x["created_at"], reverse=True)
    return results[:limit]
