"""ASGI middleware that records HTTP metrics for Prometheus.

Counts requests by (method, endpoint, status) and observes latency.
Exempts the /metrics endpoint itself from measurement.
"""

import time

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.metrics import http_requests_total, http_request_duration_seconds, metrics_enabled


class PrometheusMetricsMiddleware:
    """ASGI middleware that observes HTTP request count and latency.

    Must be registered early in the middleware stack (after RequestID)
    so it captures every request regardless of downstream failures.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not metrics_enabled() or scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "/unknown")
        # Don't measure the metrics endpoint itself
        if path.rstrip("/") in ("/metrics", "/api/v1/health"):
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        start = time.monotonic()

        # Wrap send to capture the status code
        captured_status = [200]

        async def _send_with_capture(message):  # type: ignore[no-untyped-def]
            if message.get("type") == "http.response.start":
                captured_status[0] = message.get("status", 200)
            await send(message)

        try:
            await self.app(scope, receive, _send_with_capture)
        finally:
            elapsed = time.monotonic() - start
            status = captured_status[0]
            # Normalise path — replace dynamic segments with a placeholder
            normalised = _normalise_path(path)
            http_requests_total.labels(method=method, endpoint=normalised, status=str(status)).inc()
            http_request_duration_seconds.labels(method=method, endpoint=normalised).observe(elapsed)


def _normalise_path(path: str) -> str:
    """Replace numeric/hex path segments with ``:id`` placeholder.

    ``/api/v1/tasks/42`` → ``/api/v1/tasks/:id``
    ``/api/v1/tenants/1/quota`` → ``/api/v1/tenants/:id/quota``
    """
    parts = path.strip("/").split("/")
    result: list[str] = []
    for part in parts:
        # Treat all-digit or hex segments as IDs
        if part.isdigit() or (part.startswith("0x") and all(c in "0123456789abcdefABCDEF" for c in part[2:])):
            result.append(":id")
        else:
            result.append(part)
    return "/" + "/".join(result)
