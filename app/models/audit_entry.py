"""AuditEntry — immutable SHA256-hash-linked audit trail."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditEntry(Base):
    """A single entry in the tenant-scoped SHA256 hash-chain audit log.

    Each entry's ``hash`` is computed from the previous entry's hash,
    the current timestamp, tenant, and payload — creating a tamper-evident
    linked chain analogous to blockchain but without the consensus overhead.
    """

    __tablename__ = "audit_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"), nullable=False, index=True
    )
    entry_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )  # agent_run, model_call, task_create, config_change, quota_action
    entry_id: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # The ID of the tracked resource
    action: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # created, updated, deleted, blocked, approved
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    @classmethod
    def compute_hash(
        cls,
        previous_hash: str,
        tenant_id: int,
        entry_type: str,
        entry_id: str,
        action: str,
        payload: str | None,
    ) -> str:
        """Compute the SHA256 hash for an audit entry.

        Formula: SHA256(f"{previous_hash}:{tenant_id}:{entry_type}:{entry_id}:{action}:{payload}")
        """
        raw = f"{previous_hash}:{tenant_id}:{entry_type}:{entry_id}:{action}:{payload or ''}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
