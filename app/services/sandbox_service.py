"""Sandbox testing bed — validates agent actions before execution.

Acts as a safety net: every agent action is checked against safety rules
before hitting production data.  Actions that violate rules are either
blocked outright or queued for human approval.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SANDBOX_DIR = Path(os.environ.get("SANDBOX_DATA_DIR", ".sandbox"))
PENDING_FILE = SANDBOX_DIR / "pending_actions.json"
REJECTED_FILE = SANDBOX_DIR / "rejected_actions.json"
SANDBOX_ENABLED = os.environ.get("SANDBOX_ENABLED", "true").lower() in ("true", "1")

# ─── Safety Rules ───────────────────────────────────────────────────────────
# Each rule: (rule_id, level, description)
#   level="block"   → action is always rejected
#   level="approval" → action queued for human review
#   level="warn"    → action allowed but logged
SAFETY_RULES: list[dict[str, Any]] = [
    {
        "id": "block_delete",
        "level": "block",
        "scope": "all",
        "description": "Prevent any record deletion in sandbox mode",
        "match": {"action_type": "delete"},
    },
    {
        "id": "finance_change",
        "level": "approval",
        "scope": "agent:finance",
        "description": "Finance agent actions need human approval (budget moves)",
        "match": {"agent_type": ["finance"]},
    },
    {
        "id": "order_high_value",
        "level": "approval",
        "scope": "action:accept_order",
        "description": "Orders ≥ ¥10,000 need human approval",
        "match": {"action_type": "accept_order", "min_budget": 1000000},  # cents = ¥10K
    },
]


def _ensure_dir() -> None:
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _save_json(path: Path, data: list[dict]) -> None:
    _ensure_dir()
    path.write_text(json.dumps(data, indent=2, default=str))


# ─── Public API ─────────────────────────────────────────────────────────────


def check_action(
    action_type: str,
    agent_type: str | None = None,
    budget_cents: int | None = None,
    metadata: dict | None = None,
) -> dict:
    """Check an action against safety rules.

    Returns a verdict dict:
      {"verdict": "allow"|"block"|"pending", "rule_id": str|None, "message": str}
    """
    if not SANDBOX_ENABLED:
        return {"verdict": "allow", "rule_id": None, "message": "Sandbox disabled"}

    for rule in SAFETY_RULES:
        match = rule["match"]

        # Check action_type match
        if "action_type" in match:
            if action_type != match["action_type"] and (
                not isinstance(match.get("action_type"), list)
                or action_type not in match["action_type"]
            ):
                continue

        # Check agent_type match
        if "agent_type" in match:
            if agent_type not in match["agent_type"]:
                continue

        # Check budget threshold
        if "min_budget" in match:
            if budget_cents is None or budget_cents < match["min_budget"]:
                continue

        # Rule matched
        if rule["level"] == "block":
            return {
                "verdict": "block",
                "rule_id": rule["id"],
                "message": rule["description"],
            }
        elif rule["level"] == "approval":
            return {
                "verdict": "pending",
                "rule_id": rule["id"],
                "message": rule["description"],
            }
        elif rule["level"] == "warn":
            pass  # Logged below, continue

    return {"verdict": "allow", "rule_id": None, "message": "Action allowed"}


def submit_pending_action(
    action_type: str,
    agent_type: str,
    summary: str,
    payload: dict | None = None,
    rule_id: str | None = None,
) -> dict:
    """Submit an action for human approval.

    Returns the created pending action record.
    """
    pending = _load_json(PENDING_FILE)
    record = {
        "id": len(pending) + 1,
        "action_type": action_type,
        "agent_type": agent_type,
        "summary": summary,
        "payload": payload or {},
        "rule_id": rule_id,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    pending.append(record)
    _save_json(PENDING_FILE, pending)
    return record


def get_pending_actions(status: str | None = None) -> list[dict]:
    """List pending actions, optionally filtered by status."""
    actions = _load_json(PENDING_FILE)
    if status:
        actions = [a for a in actions if a["status"] == status]
    return sorted(actions, key=lambda a: a["created_at"], reverse=True)


def get_pending_action(action_id: int) -> dict | None:
    """Get a single pending action by ID."""
    for a in _load_json(PENDING_FILE):
        if a["id"] == action_id:
            return a
    return None


def approve_action(action_id: int, reviewer: str = "hq") -> dict | None:
    """Approve a pending action."""
    actions = _load_json(PENDING_FILE)
    for a in actions:
        if a["id"] == action_id:
            a["status"] = "approved"
            a["reviewed_at"] = datetime.now(timezone.utc).isoformat()
            a["reviewed_by"] = reviewer
            _save_json(PENDING_FILE, actions)
            return a
    return None


def reject_action(action_id: int, reason: str = "", reviewer: str = "hq") -> dict | None:
    """Reject a pending action."""
    actions = _load_json(PENDING_FILE)
    rejected = _load_json(REJECTED_FILE)
    for a in actions:
        if a["id"] == action_id:
            a["status"] = "rejected"
            a["rejected_reason"] = reason
            a["reviewed_at"] = datetime.now(timezone.utc).isoformat()
            a["reviewed_by"] = reviewer
            rejected.append(a)
            actions = [x for x in actions if x["id"] != action_id]
            _save_json(PENDING_FILE, actions)
            _save_json(REJECTED_FILE, rejected)
            return a
    return None


def get_sandbox_summary() -> dict:
    """Get sandbox stats for HQ display."""
    pending = _load_json(PENDING_FILE)
    rejected = _load_json(REJECTED_FILE)
    pending_active = [a for a in pending if a["status"] == "pending"]
    return {
        "sandbox_enabled": SANDBOX_ENABLED,
        "total_pending": len(pending),
        "pending_approval": len(pending_active),
        "approved": sum(1 for a in pending if a["status"] == "approved"),
        "total_rejected": len(rejected),
        "recent": pending[:5] if pending else [],
        "rules": len(SAFETY_RULES),
    }


def cleanup_expired(hours: int = 72) -> int:
    """Move expired pending actions to rejected."""
    actions = _load_json(PENDING_FILE)
    rejected = _load_json(REJECTED_FILE)
    now = datetime.now(timezone.utc)
    kept, expired = [], []
    for a in actions:
        created = datetime.fromisoformat(a["created_at"])
        if (now - created).total_seconds() > hours * 3600 and a["status"] == "pending":
            a["status"] = "expired"
            a["reviewed_at"] = now.isoformat()
            expired.append(a)
        else:
            kept.append(a)
    if expired:
        rejected.extend(expired)
        _save_json(PENDING_FILE, kept)
        _save_json(REJECTED_FILE, rejected)
    return len(expired)
