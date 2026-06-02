"""Integration tests for the Interrupts API endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestListPending:
    def test_pending_returns_list(self):
        resp = client.get("/api/v1/interrupts/pending")
        assert resp.status_code == 200
        data = resp.json()
        assert "interrupts" in data

    def test_list_all_returns_list(self):
        resp = client.get("/api/v1/interrupts")
        assert resp.status_code == 200
        data = resp.json()
        assert "interrupts" in data


class TestCreate:
    def test_create_requires_required_fields(self):
        resp = client.post("/api/v1/interrupts", json={})
        assert resp.status_code == 422  # validation error

    def test_create_minimal(self):
        resp = client.post("/api/v1/interrupts", json={
            "agent_type": "test-agent", "task_id": 1, "reason": "test"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["interrupt_id"] > 0


class TestDecide:
    def test_approve_nonexistent(self):
        resp = client.post("/api/v1/interrupts/99999/approve")
        assert resp.status_code == 404

    def test_reject_nonexistent(self):
        resp = client.post("/api/v1/interrupts/99999/reject", json={"reason": "no"})
        assert resp.status_code == 404

    def test_create_then_approve(self):
        create = client.post("/api/v1/interrupts", json={
            "agent_type": "test-agent", "task_id": 2, "reason": "test"
        })
        iid = create.json()["interrupt_id"]
        # Approve
        resp = client.post(f"/api/v1/interrupts/{iid}/approve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
        # Double approve fails
        resp = client.post(f"/api/v1/interrupts/{iid}/approve")
        assert resp.status_code == 404

    def test_create_then_reject(self):
        create = client.post("/api/v1/interrupts", json={
            "agent_type": "test-agent", "task_id": 3, "reason": "test"
        })
        iid = create.json()["interrupt_id"]
        resp = client.post(f"/api/v1/interrupts/{iid}/reject", json={"reason": "Not needed"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"
        assert resp.json()["reason"] == "Not needed"
