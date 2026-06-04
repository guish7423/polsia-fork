"""Tests for the SHA256 hash-chain audit service."""

import json

import pytest

from app.models.audit_entry import AuditEntry
from app.services.audit_chain import append_entry, get_entries, verify_chain


@pytest.mark.asyncio
async def test_append_entry_creates_hash(async_db_session):
    """Appending an entry must compute and store a valid SHA256 hash."""
    entry = await append_entry(
        async_db_session,
        tenant_id=1,
        entry_type="agent_run",
        entry_id="42",
        action="completed",
        payload={"agent_type": "test", "duration": 1.5},
    )
    await async_db_session.commit()
    assert entry.id > 0
    assert entry.hash is not None
    assert len(entry.hash) == 64
    assert entry.previous_hash == "0" * 64  # first entry


@pytest.mark.asyncio
async def test_append_entry_links_to_previous(async_db_session):
    """Second entry's previous_hash must match the first entry's hash."""
    e1 = await append_entry(
        async_db_session, tenant_id=1, entry_type="task_create", entry_id="1", action="created"
    )
    e2 = await append_entry(
        async_db_session, tenant_id=1, entry_type="task_create", entry_id="2", action="created"
    )
    await async_db_session.commit()
    assert e2.previous_hash == e1.hash


@pytest.mark.asyncio
async def test_verify_chain_passes_on_integrity(async_db_session):
    """A valid chain must pass verification with zero broken links."""
    await append_entry(
        async_db_session, tenant_id=1, entry_type="agent_run", entry_id="1", action="started"
    )
    await append_entry(
        async_db_session, tenant_id=1, entry_type="agent_run", entry_id="1", action="completed"
    )
    await async_db_session.commit()
    broken = await verify_chain(async_db_session, tenant_id=1)
    assert len(broken) == 0


@pytest.mark.asyncio
async def test_verify_chain_detects_tampered_entry(async_db_session):
    """Modifying an entry's payload must break the chain."""
    await append_entry(
        async_db_session, tenant_id=1, entry_type="agent_run", entry_id="1", action="started"
    )
    await append_entry(
        async_db_session, tenant_id=1, entry_type="agent_run", entry_id="1", action="completed"
    )
    await async_db_session.commit()

    # Tamper with the first entry
    from sqlalchemy import update

    stmt = (
        update(AuditEntry)
        .where(AuditEntry.tenant_id == 1, AuditEntry.entry_id == "1")
        .values(payload=json.dumps({"tampered": True}))
    )
    await async_db_session.execute(stmt)
    await async_db_session.commit()

    broken = await verify_chain(async_db_session, tenant_id=1)
    assert len(broken) > 0


@pytest.mark.asyncio
async def test_get_entries_filters_by_type(async_db_session):
    """get_entries must return only matching entry types."""
    await append_entry(
        async_db_session, tenant_id=1, entry_type="agent_run", entry_id="1", action="started"
    )
    await append_entry(
        async_db_session, tenant_id=1, entry_type="task_create", entry_id="10", action="created"
    )
    await async_db_session.commit()
    runs = await get_entries(async_db_session, tenant_id=1, entry_type="agent_run")
    assert len(runs) == 1
    assert runs[0].entry_type == "agent_run"
