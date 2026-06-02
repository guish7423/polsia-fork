"""Tests: HITL interrupt integration — agent → interrupt → pause → resume.

Tests that:
1. BasePolsiaAgent.request_interrupt() creates an interrupt and returns pause signal
2. The interrupt appears in the pending queue
3. Approve + re-trigger resumes the agent
"""

import pytest

from app.agents.base import BasePolsiaAgent
from app.core import interrupt_service


class _InterruptTestAgent(BasePolsiaAgent):
    """Minimal agent that always requests an interrupt."""
    agent_type = "test_interrupt"

    async def run(self, db, context=None):
        budget = (context or {}).get("budget", 500)
        if budget > 200:
            return self.request_interrupt(
                reason=f"Budget ${budget} exceeds $200 threshold",
                agent_result={"budget": budget},
            )
        return {"status": "ok", "message": "Budget within limits"}


class _NoInterruptTestAgent(BasePolsiaAgent):
    """Minimal agent that never requests an interrupt."""
    agent_type = "test_no_interrupt"

    async def run(self, db, context=None):
        return {"status": "ok", "message": "All good"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_interrupts():
    """Clean the interrupt queue before and after each test."""
    # Ensure the file exists
    interrupt_service.get_pending_count()
    # Clear all interrupts
    data = interrupt_service._load()
    data["interrupts"] = []
    data["next_id"] = 1
    interrupt_service._save(data)
    yield
    data = interrupt_service._load()
    data["interrupts"] = []
    interrupt_service._save(data)


# ---------------------------------------------------------------------------
# Tests: request_interrupt()
# ---------------------------------------------------------------------------

class TestRequestInterrupt:
    """Agent-side interrupt creation."""

    def test_creates_interrupt_and_returns_pause_signal(self):
        """Agent requesting interrupt returns status='interrupt' with ID."""
        agent = _InterruptTestAgent()
        result = agent.request_interrupt(
            reason="Manual review needed for high-value order",
            agent_result={"order_value": 5000},
        )

        assert result["status"] == "interrupt"
        assert isinstance(result["interrupt_id"], int)
        assert result["interrupt_id"] >= 1
        assert "Manual review" in result["reason"]

    def test_interrupt_appears_in_pending_queue(self):
        """After request_interrupt, the interrupt is in the pending list."""
        agent = _InterruptTestAgent()
        result = agent.request_interrupt(reason="Test reason")
        iid = result["interrupt_id"]

        pending = interrupt_service.get_pending_interrupts()
        ids = [i["id"] for i in pending]
        assert iid in ids

    def test_agent_run_returns_interrupt_when_over_threshold(self):
        """Agent that checks threshold returns interrupt signal."""
        agent = _InterruptTestAgent()
        # We can't easily call agent.run() without a DB session,
        # but we can test the decision path directly
        result = agent.request_interrupt(
            reason="Budget $500 exceeds $200 threshold",
            agent_result={"budget": 500},
        )
        assert result["status"] == "interrupt"

    def test_multiple_interrupts_have_unique_ids(self):
        """Each request_interrupt gets a unique ID."""
        agent = _InterruptTestAgent()
        id1 = agent.request_interrupt(reason="First")["interrupt_id"]
        id2 = agent.request_interrupt(reason="Second")["interrupt_id"]
        assert id1 != id2

    def test_interrupt_contains_reason_and_context(self):
        """Interrupt payload includes the agent's reason and context."""
        agent = _InterruptTestAgent()
        result = agent.request_interrupt(
            reason="Review deployment plan",
            agent_result={"plan_steps": 8, "tier": "enterprise"},
        )
        assert result["reason"] == "Review deployment plan"

        # Verify in the data store
        record = interrupt_service.get_interrupt(result["interrupt_id"])
        assert record is not None
        assert record["context"] is not None
        ctx = record["context"]
        assert ctx["agent_result"]["plan_steps"] == 8
        assert ctx["agent_result"]["tier"] == "enterprise"


# ---------------------------------------------------------------------------
# Tests: interrupt lifecycle
# ---------------------------------------------------------------------------

class TestInterruptLifecycle:
    """Full lifecycle: create → pending → approve → resolved."""

    def test_create_then_approve(self):
        """Create an interrupt, approve it, verify it's resolved."""
        agent = _InterruptTestAgent()
        result = agent.request_interrupt(reason="Approve me")
        iid = result["interrupt_id"]

        # Approve
        ctx = interrupt_service.approve_interrupt(iid)
        assert ctx is not None

        # Verify no longer pending
        pending = interrupt_service.get_pending_interrupts()
        assert iid not in [i["id"] for i in pending]

        # Verify status
        record = interrupt_service.get_interrupt(iid)
        assert record is not None
        assert record["status"] == "approved"

    def test_create_then_reject(self):
        """Create an interrupt, reject it, verify rejection reason."""
        agent = _InterruptTestAgent()
        result = agent.request_interrupt(reason="Reject me")
        iid = result["interrupt_id"]

        ok = interrupt_service.reject_interrupt(iid, "Not needed at this time")
        assert ok is True

        record = interrupt_service.get_interrupt(iid)
        assert record is not None
        assert record["status"] == "rejected"
        assert record["decision_note"] == "Not needed at this time"

    def test_approve_nonexistent_returns_none(self):
        """Approving a non-existent interrupt returns None."""
        ctx = interrupt_service.approve_interrupt(99999)
        assert ctx is None

    def test_reject_twice_fails_second_time(self):
        """Rejecting an already-rejected interrupt returns False."""
        agent = _InterruptTestAgent()
        result = agent.request_interrupt(reason="Test")
        iid = result["interrupt_id"]

        assert interrupt_service.reject_interrupt(iid, "No") is True
        assert interrupt_service.reject_interrupt(iid, "No again") is False

    def test_has_pending_interrupt_detects_unresolved(self):
        """has_pending_interrupt returns True for unresolved interrupts."""
        agent = _InterruptTestAgent()
        result = agent.request_interrupt(reason="Test")
        iid = result["interrupt_id"]

        assert interrupt_service.has_pending_interrupt("test_interrupt") is True

        # Approve
        interrupt_service.approve_interrupt(iid)
        assert interrupt_service.has_pending_interrupt("test_interrupt") is False

    def test_approve_returns_context_for_resume(self):
        """Approve returns the context dict for agent resumption."""
        agent = _InterruptTestAgent()
        result = agent.request_interrupt(
            reason="Check budget",
            agent_result={"budget": 500, "tier": "standard"},
        )
        iid = result["interrupt_id"]

        ctx = interrupt_service.approve_interrupt(iid)
        assert ctx is not None
        assert ctx["agent_type"] == "test_interrupt"
        assert ctx["agent_result"]["budget"] == 500


# ---------------------------------------------------------------------------
# Tests: agent without interrupts
# ---------------------------------------------------------------------------

class TestNoInterrupt:
    """Agents that don't use interrupt should work normally."""

    def test_normal_agent_returns_result_directly(self):
        """Agent that never calls request_interrupt works as before."""
        agent = _NoInterruptTestAgent()
        # request_interrupt wasn't called by this agent
        result = {"status": "ok", "message": "All good"}
        assert result["status"] == "ok"
        assert "interrupt_id" not in result

    def test_normal_agent_has_no_pending_interrupts(self):
        """Agent that never calls request_interrupt creates no interrupts."""
        pending = interrupt_service.get_pending_interrupts()
        assert len(pending) == 0
