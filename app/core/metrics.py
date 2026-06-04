"""Prometheus metrics definitions for CrossWave observability.

Provides counters, histograms, and gauges for:
- HTTP API requests (count, latency, status)
- Agent runs (count, duration, status)
- LLM calls (count, duration, tokens, provider)
- Task queue depth
- Active alerts
"""

import time
from functools import wraps

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

    # Stub classes so the module is always importable
    class _StubMetric:
        def labels(self, **kwargs):  # type: ignore[no-untyped-def]
            return self
        def inc(self, amount=1):  # type: ignore[no-untyped-def]
            pass
        def observe(self, amount):  # type: ignore[no-untyped-def]
            pass
        def set(self, value):  # type: ignore[no-untyped-def]
            pass

    class _Registry:
        _stub = _StubMetric()
        def get_sample_value(self, name):  # type: ignore[no-untyped-def]
            return 0

    Counter = Histogram = Gauge = lambda name, desc, *a, **kw: _StubMetric()  # type: ignore[assignment]
    REGISTRY = _Registry()
    generate_latest = lambda: b"# prometheus_client not installed\n"  # type: ignore[assignment]


# ── HTTP API metrics ───────────────────────────────────────────────────────────

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests by method, endpoint, and status code",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds by method and endpoint",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ── Agent metrics ──────────────────────────────────────────────────────────────

agent_runs_total = Counter(
    "agent_runs_total",
    "Total agent runs by agent type and status",
    ["agent_type", "status"],
)

agent_run_duration_seconds = Histogram(
    "agent_run_duration_seconds",
    "Agent run duration in seconds by agent type",
    ["agent_type"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
)

# ── LLM call metrics ──────────────────────────────────────────────────────────

llm_calls_total = Counter(
    "llm_calls_total",
    "Total LLM API calls by provider, model, and success status",
    ["provider", "model", "success"],
)

llm_call_duration_seconds = Histogram(
    "llm_call_duration_seconds",
    "LLM API call latency in seconds by provider and model",
    ["provider", "model"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 40.0, 80.0),
)

llm_tokens_total = Counter(
    "llm_tokens_total",
    "Total tokens consumed (input / output) by provider and model",
    ["provider", "model", "direction"],
)

# ── Task queue & alerts ────────────────────────────────────────────────────────

tasks_queue_depth = Gauge(
    "tasks_queue_depth",
    "Current depth of task queues by queue name",
    ["queue"],
)

alerts_active_total = Gauge(
    "alerts_active_total",
    "Current number of active alerts by severity",
    ["severity"],
)


def metrics_enabled() -> bool:
    """Shortcut to check whether prometheus_client is installed."""
    return PROMETHEUS_AVAILABLE


# ── Decorator for manual timing ───────────────────────────────────────────────

def observe_duration(histogram: Histogram, label_values: tuple):  # type: ignore[type-arg]
    """Decorator that observes the wrapped async function's duration.

    Usage::

        @observe_duration(agent_run_duration_seconds, (agent_type,))
        async def run_agent(...):
            ...
    """
    def decorator(func):  # type: ignore[no-untyped-def]
        @wraps(func)
        async def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def]
            start = time.monotonic()
            try:
                return await func(*args, **kwargs)
            finally:
                elapsed = time.monotonic() - start
                histogram.labels(*label_values).observe(elapsed)
        return wrapper
    return decorator
