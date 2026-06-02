"""Tests for the HITL Interrupt Service."""

import os
import tempfile

import pytest

from app.core import interrupt_service

# Use a temp file for each test to avoid state leakage
@pytest.fixture(autouse=True)
def _temp_interrupts_file(monkeypatch):
    """Redirect interrupts.json to a temp file for test isolation."""
    tmp = tempfile.mktemp(suffix=".json")
    monkeypatch.setattr(interrupt_service, "INTERRUPTS_FILE", tmp)
    yield
    if os.path.exists(tmp):
        os.remove(tmp)


class TestCreate:
    def test_create_returns_incrementing_ids(self):
        iid1 = interrupt_service.create_interrupt("monitor", 1, "Test reason")
        iid2 = interrupt_service.create_interrupt("evolution", 2, "Another reason")
        assert iid1 == 1
        assert iid2 == 2

    def test_create_stores_fields(self):
        iid = interrupt_service.create_interrupt(
            "finance", 42, "Large transaction", {"amount": 50000}
        )
        entry = interrupt_service.get_interrupt(iid)
        assert entry["agent_type"] == "finance"
        assert entry["task_id"] == 42
        assert entry["reason"] == "Large transaction"
        assert entry["context"] == {"amount": 50000}
        assert entry["status"] == "pending"

    def test_create_defaults_context(self):
        iid = interrupt_service.create_interrupt("scanner", 7, "Scan result")
        entry = interrupt_service.get_interrupt(iid)
        assert entry["context"] == {}


class TestApprove:
    def test_approve_returns_context(self):
        iid = interrupt_service.create_interrupt("agent", 1, "Approve me", {"key": "val"})
        ctx = interrupt_service.approve_interrupt(iid)
        assert ctx == {"key": "val"}
        entry = interrupt_service.get_interrupt(iid)
        assert entry["status"] == "approved"
        assert entry["decision"] == "approved"

    def test_approve_already_decided_returns_none(self):
        iid = interrupt_service.create_interrupt("agent", 2, "Test")
        interrupt_service.approve_interrupt(iid)
        ctx = interrupt_service.approve_interrupt(iid)
        assert ctx is None

    def test_approve_nonexistent_returns_none(self):
        ctx = interrupt_service.approve_interrupt(999)
        assert ctx is None


class TestReject:
    def test_reject_with_reason(self):
        iid = interrupt_service.create_interrupt("agent", 3, "Reject me")
        ok = interrupt_service.reject_interrupt(iid, "Not needed")
        assert ok is True
        entry = interrupt_service.get_interrupt(iid)
        assert entry["status"] == "rejected"
        assert entry["decision"] == "rejected"
        assert entry["decision_note"] == "Not needed"

    def test_reject_nonexistent_returns_false(self):
        ok = interrupt_service.reject_interrupt(999, "Nope")
        assert ok is False

    def test_reject_already_decided_returns_false(self):
        iid = interrupt_service.create_interrupt("agent", 4, "Test")
        interrupt_service.reject_interrupt(iid, "No")
        ok = interrupt_service.reject_interrupt(iid, "Still no")
        assert ok is False


class TestQuery:
    def test_get_pending_interrupts(self):
        interrupt_service.create_interrupt("a1", 1, "Reason")
        interrupt_service.create_interrupt("a2", 2, "Reason")
        pending = interrupt_service.get_pending_interrupts()
        assert len(pending) == 2

    def test_get_pending_filter_by_agent(self):
        iid = interrupt_service.create_interrupt("monitor", 1, "Reason")
        interrupt_service.create_interrupt("evolution", 2, "Reason")
        monitor_pending = interrupt_service.get_pending_interrupts("monitor")
        assert len(monitor_pending) == 1
        assert monitor_pending[0]["id"] == iid

    def test_pending_excludes_decided(self):
        iid = interrupt_service.create_interrupt("agent", 1, "Reason")
        interrupt_service.approve_interrupt(iid)
        pending = interrupt_service.get_pending_interrupts()
        assert len(pending) == 0

    def test_has_pending(self):
        interrupt_service.create_interrupt("agent", 1, "Reason")
        assert interrupt_service.has_pending_interrupt("agent") is True
        assert interrupt_service.has_pending_interrupt("other") is False

    def test_has_pending_with_task_id(self):
        interrupt_service.create_interrupt("agent", 42, "Reason")
        assert interrupt_service.has_pending_interrupt("agent", 42) is True
        assert interrupt_service.has_pending_interrupt("agent", 99) is False

    def test_pending_count(self):
        assert interrupt_service.get_pending_count() == 0
        interrupt_service.create_interrupt("a1", 1, "R1")
        interrupt_service.create_interrupt("a2", 2, "R2")
        assert interrupt_service.get_pending_count() == 2

    def test_get_interrupt_nonexistent(self):
        assert interrupt_service.get_interrupt(999) is None

    def test_list_all_ordering(self):
        interrupt_service.create_interrupt("a1", 1, "First")
        interrupt_service.create_interrupt("a2", 2, "Second")
        results = interrupt_service.list_all()
        assert len(results) == 2
        # newest first
        assert results[0]["id"] == 2
        assert results[1]["id"] == 1

    def test_list_all_filters(self):
        iid = interrupt_service.create_interrupt("monitor", 1, "Reason")
        interrupt_service.create_interrupt("evolution", 2, "Reason")
        interrupt_service.approve_interrupt(iid)
        # filter by status
        pending = interrupt_service.list_all(status="pending")
        assert len(pending) == 1
        # filter by agent
        evo = interrupt_service.list_all(agent_type="evolution")
        assert len(evo) == 1
