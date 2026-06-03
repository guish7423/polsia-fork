"""Structured JSON logging and request-ID middleware.

Provides:
- ``JSONFormatter`` — Python logging formatter that outputs JSON lines.
- ``RequestIDMiddleware`` — adds a unique ``X-Request-ID`` header + ``request.state.request_id``.
- ``setup_logging`` — configure the root logger with JSON output.
"""

import json
import logging
import time
import uuid

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send


class JSONFormatter(logging.Formatter):
    """Log formatter that emits JSON lines.

    Every log record is serialised as a single JSON object with
    ``timestamp``, ``level``, ``name``, ``message``, and optional
    ``exception`` fields.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, object] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data, default=str)


class RequestIDMiddleware:
    """Add a unique request ID to every request.

    Implemented as raw ASGI to be truly outermost — it intercepts the
    response at the ASGI level, so the ``X-Request-ID`` header is set
    even when downstream middleware or handlers raise exceptions.

    The ID is also stored in ``request.state.request_id`` for use by
    downstream middleware and exception handlers.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())

        # Inject request_id into the ASGI scope so Starlette's Request
        # object can pick it up via request.state.
        scope["state"] = {**scope.get("state", {}), "request_id": request_id}

        original_send = send

        async def send_with_header(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append(
                    (b"X-Request-ID", request_id.encode())
                )
                message["headers"] = headers
            await original_send(message)

        await self.app(scope, receive, send_with_header)


class RequestLoggingMiddleware:
    """Log every request and its response (method, path, status, duration).

    Implemented as raw ASGI to correctly handle exceptions raised by
    downstream handlers — ASGI middleware has no ``call_next`` re-raise
    issue that ``BaseHTTPMiddleware`` has.

    Depends on ``RequestIDMiddleware`` having run first so that
    ``request.state.request_id`` is present.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        request = Request(scope)
        request_id: str = scope.get("state", {}).get("request_id", "unknown")

        _log_request(request, request_id)

        original_send = send

        async def send_with_log(message: dict) -> None:
            if message["type"] == "http.response.start":
                status_code = message.get("status", 0)
                _access_logger.info(
                    json.dumps(
                        {
                            "event": "response",
                            "method": request.method,
                            "path": str(request.url),
                            "status_code": status_code,
                            "duration_ms": round((time.time() - start_time) * 1000, 2),
                            "request_id": request_id,
                        }
                    )
                )
            await original_send(message)

        try:
            await self.app(scope, receive, send_with_log)
        except Exception:
            duration = time.time() - start_time
            _access_logger.info(
                json.dumps(
                    {
                        "event": "error",
                        "method": request.method,
                        "path": str(request.url),
                        "duration_ms": round(duration * 1000, 2),
                        "request_id": request_id,
                    }
                )
            )
            raise


def setup_logging(name: str = "polsia") -> None:
    """Configure the root logger with JSON output to stderr.

    Call once during application startup.  Safe to call multiple times
    (duplicate handlers are silently skipped).
    """
    logger = logging.getLogger(name)
    if any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        return  # already configured
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    logger.propagate = False


# ─── Internal helpers ──────────────────────────────────────────────────────────

_access_logger = logging.getLogger("polsia.access")


def _log_request(request: Request, request_id: str) -> None:
    _access_logger.info(
        json.dumps(
            {
                "event": "request",
                "method": request.method,
                "path": str(request.url),
                "request_id": request_id,
            }
        )
    )


def _log_response(request: Request, response: Response, start_time: float, request_id: str) -> None:
    duration = time.time() - start_time
    _access_logger.info(
        json.dumps(
            {
                "event": "response",
                "method": request.method,
                "path": str(request.url),
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2),
                "request_id": request_id,
            }
        )
    )
