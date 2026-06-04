"""AuditChainService — append-only SHA256 hash-chain audit trail.

Usage:
    entry = await append_entry(db, tenant_id, "agent_run", "42", "completed",
                                {"agent_type": "orchestrator", "duration": 12.5})
"""

from __future__ import annotations

import json

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_entry import AuditEntry


async def _get_latest_hash(db: AsyncSession, tenant_id: int) -> str | None:
    """Return the SHA256 hash of the latest entry for this tenant."""
    q = (
        select(AuditEntry.hash)
        .where(AuditEntry.tenant_id == tenant_id)
        .order_by(desc(AuditEntry.id))
        .limit(1)
    )
    result = await db.execute(q)
    row = result.scalar_one_or_none()
    return row


async def append_entry(
    db: AsyncSession,
    tenant_id: int,
    entry_type: str,
    entry_id: str,
    action: str,
    payload: dict | None = None,
) -> AuditEntry:
    """Append a new entry to the audit chain.

    Computes the SHA256 hash from the previous entry's hash and persists
    the new entry. This is fire-and-forget — never raises on failure.
    """
    try:
        previous_hash = await _get_latest_hash(db, tenant_id) or ("0" * 64)
        payload_str = json.dumps(payload, default=str) if payload else None

        entry_hash = AuditEntry.compute_hash(
            previous_hash=previous_hash,
            tenant_id=tenant_id,
            entry_type=entry_type,
            entry_id=entry_id,
            action=action,
            payload=payload_str,
        )

        entry = AuditEntry(
            tenant_id=tenant_id,
            entry_type=entry_type,
            entry_id=entry_id,
            action=action,
            payload=payload_str,
            previous_hash=previous_hash,
            hash=entry_hash,
        )
        db.add(entry)
        await db.flush()
        return entry
    except Exception:
        # Fire-and-forget: never block the caller
        import logging

        logging.getLogger(__name__).exception(
            "Failed to append audit entry for tenant %s", tenant_id
        )
        # Return a stub so callers don't need None-check
        return AuditEntry(
            id=0,
            tenant_id=tenant_id,
            entry_type=entry_type,
            entry_id=entry_id,
            action=action,
            hash="0" * 64,
        )


async def verify_chain(db: AsyncSession, tenant_id: int) -> list[dict]:
    """Walk the chain and verify hash integrity.

    Returns a list of broken-link reports. An empty list means the chain
    is intact.
    """
    q = (
        select(AuditEntry)
        .where(AuditEntry.tenant_id == tenant_id)
        .order_by(AuditEntry.id)
    )
    result = await db.execute(q)
    entries = result.scalars().all()

    broken: list[dict] = []
    expected_prev = "0" * 64

    for entry in entries:
        issues = []

        # Check previous_hash linkage
        if entry.previous_hash != expected_prev:
            issues.append(
                {
                    "type": "broken_link",
                    "expected_previous": expected_prev,
                    "actual_previous": entry.previous_hash,
                }
            )

        # Recompute hash from stored data to detect payload tampering
        recomputed = AuditEntry.compute_hash(
            previous_hash=entry.previous_hash,
            tenant_id=entry.tenant_id,
            entry_type=entry.entry_type,
            entry_id=entry.entry_id,
            action=entry.action,
            payload=entry.payload,
        )
        if recomputed != entry.hash:
            issues.append(
                {
                    "type": "hash_mismatch",
                    "stored_hash": entry.hash,
                    "recomputed_hash": recomputed,
                }
            )

        if issues:
            broken.append({"id": entry.id, "issues": issues})

        expected_prev = entry.hash

    return broken


async def get_entries(
    db: AsyncSession,
    tenant_id: int,
    entry_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AuditEntry]:
    """List audit entries for a tenant, optionally filtered by type."""
    q = select(AuditEntry).where(AuditEntry.tenant_id == tenant_id)
    if entry_type:
        q = q.where(AuditEntry.entry_type == entry_type)
    q = q.order_by(desc(AuditEntry.id)).limit(limit).offset(offset)
    result = await db.execute(q)
    return list(result.scalars().all())
