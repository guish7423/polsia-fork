"""AgentMessage — durable inter-agent message storage."""

from __future__ import annotations

import datetime
from datetime import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class AgentMessage(Base):
    """A durable inter-agent message in the agent mesh."""

    __tablename__ = "agent_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)

    # Routing
    sender_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    """Agent type that sent this message (e.g. 'competitor_research')."""
    recipient_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    """Agent type that should receive this message. None = broadcast."""
    target_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """If this is a reply, the original message ID."""

    # Content
    message_type: Mapped[str] = mapped_column(String(32), nullable=False, default="generic")
    """Message classification: 'generic', 'delegation', 'broadcast', 'capability_query', 'result'."""
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    body: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    """JSON payload with message data."""

    # Status — managed at Python level via constants, matching existing Task pattern
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    """One of: pending, delivered, read, failed."""
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    """1-5 priority (5 = highest)."""

    # Metadata
    ttl_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=86400)
    """Auto-expire after this many seconds."""
    created_at: Mapped[dt] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True,
    )
    delivered_at: Mapped[dt | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[dt | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
