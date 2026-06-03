"""Agent run model — tracks execution lifecycle and telemetry."""

from datetime import datetime

from sqlalchemy import func, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"))
    agent_type: Mapped[str] = mapped_column(String(100), nullable=False)
    run_type: Mapped[str] = mapped_column(String(100), server_default="task")
    status: Mapped[str] = mapped_column(String(50), server_default="running")
    input_context: Mapped[dict | None] = mapped_column(JSON)
    output: Mapped[dict | None] = mapped_column(JSON)
    raw_log: Mapped[str | None] = mapped_column(Text)

    # ── Telemetry ──────────────────────────────────────────────────────────
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    """Total tokens (input+output) consumed during this run."""
    cost_usd: Mapped[float | None] = mapped_column(Float)
    """Aggregated LLM cost for this run in USD."""
    duration_secs: Mapped[float | None] = mapped_column(Float)
    """Wall-clock execution duration in seconds."""
    llm_call_count: Mapped[int | None] = mapped_column(Integer)
    """Number of LLM API calls made during this run."""

    execution_spans: Mapped[dict | None] = mapped_column(JSON)
    """Structured timeline of execution events.::

        [
            {
                "span_type": "llm_call" | "tool_call" | "state_transition" | "interrupt",
                "started_at": "2025-06-03T10:00:00Z",
                "duration_ms": 1234,
                "detail": { ... }   # span-type-specific payload
            }
        ]
    """

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
