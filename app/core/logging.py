"""Structured logging module — JSON in production, human-readable in dev."""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class StructuredFormatter(logging.Formatter):
    """Output JSON logs in production; human-readable colored in development."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        if hasattr(record, "extra"):
            log_entry.update(record.extra)  # type: ignore

        if getattr(record, "is_dev", False):
            # Human-readable
            parts = [
                f"[{record.levelname:^8}]",
                f"{log_entry['ts'][:19]}",
                f"{record.name}",
                record.getMessage(),
            ]
            if hasattr(record, "duration_ms"):
                parts.append(f"({record.duration_ms}ms)")
            return "  ".join(parts)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(level: str = "INFO", is_dev: bool = True) -> None:
    """Configure root logger with structured output."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove default handlers
    for h in root.handlers[:]:
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    fmt = StructuredFormatter()
    handler.setFormatter(fmt)
    # Attach is_dev to each record for formatting choice
    handler.addFilter(lambda r: setattr(r, "is_dev", is_dev) or True)
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Get a structured logger for the given module name."""
    return logging.getLogger(name)
