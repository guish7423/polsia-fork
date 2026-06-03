"""Tests for JSON logging and request-ID middleware."""
import json
import logging
import sys
import uuid

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from app.core.logging import (
    JSONFormatter,
    RequestIDMiddleware,
    RequestLoggingMiddleware,
    setup_logging,
)


# ─── JSONFormatter ──────────────────────────────────────────────────────────────


class TestJSONFormatter:
    def test_basic_format(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger", level=logging.INFO, pathname=__file__, lineno=1,
            msg="hello world", args=(), exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["name"] == "test_logger"
        assert data["message"] == "hello world"
        assert "timestamp" in data

    def test_handles_exception(self):
        formatter = JSONFormatter()
        try:
            1 / 0
        except ZeroDivisionError:
            record = logging.LogRecord(
                name="err", level=logging.ERROR, pathname=__file__, lineno=1,
                msg="boom", args=(), exc_info=sys.exc_info(),
            )
        output = formatter.format(record)
        data = json.loads(output)
        assert "exception" in data
        assert "ZeroDivisionError" in data["exception"]

    def test_handles_non_string_message(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="t", level=logging.WARNING, pathname=__file__, lineno=1,
            msg={"key": "val"}, args=(), exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["message"] == "{'key': 'val'}"


# ─── setup_logging ──────────────────────────────────────────────────────────────


class TestSetupLogging:
    def test_setup_logging_idempotent(self):
        setup_logging("test_idempotent")
        count_before = len(logging.getLogger("test_idempotent").handlers)
        setup_logging("test_idempotent")
        count_after = len(logging.getLogger("test_idempotent").handlers)
        assert count_before == count_after


# ─── RequestIDMiddleware (raw ASGI) ─────────────────────────────────────────────


class TestRequestIDMiddleware:
    @pytest.mark.asyncio
    async def test_sets_request_id_and_header(self):
        app = FastAPI()

        @app.get("/ping")
        async def ping(request: Request):
            return {"request_id": request.state.request_id}

        app.add_middleware(RequestIDMiddleware)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/ping")

        assert resp.status_code == 200
        data = resp.json()
        assert uuid.UUID(data["request_id"])  # valid UUID
        assert resp.headers.get("X-Request-ID") == data["request_id"]

    @pytest.mark.asyncio
    async def test_each_request_gets_unique_id(self):
        app = FastAPI()

        @app.get("/ping")
        async def ping(request: Request):
            return {"request_id": request.state.request_id}

        app.add_middleware(RequestIDMiddleware)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp1 = await client.get("/ping")
            resp2 = await client.get("/ping")

        assert resp1.json()["request_id"] != resp2.json()["request_id"]

    @pytest.mark.asyncio
    async def test_header_on_error_response(self):
        """X-Request-ID should be set even for error responses."""
        from fastapi.responses import JSONResponse
        from starlette.exceptions import HTTPException

        app = FastAPI()

        @app.get("/error")
        async def error():
            raise HTTPException(status_code=404, detail="Not found")

        app.add_middleware(RequestIDMiddleware)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/error")

        assert resp.status_code == 404
        assert resp.headers.get("X-Request-ID") is not None


# ─── RequestLoggingMiddleware (raw ASGI) ────────────────────────────────────────


class TestRequestLoggingMiddleware:
    @pytest.mark.asyncio
    async def test_does_not_break_normal_responses(self):
        app = FastAPI()

        @app.get("/hello")
        async def hello():
            return {"ok": True}

        app.add_middleware(RequestIDMiddleware)
        app.add_middleware(RequestLoggingMiddleware)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/hello")

        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        assert resp.headers.get("X-Request-ID") is not None


# Need to ensure lifespan does not interfere
from contextlib import asynccontextmanager  # noqa: E402
