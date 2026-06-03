"""Standardized error response models."""
from enum import Enum

from pydantic import BaseModel


class ErrorCode(str, Enum):
    """Enumerated error codes for structured API responses."""

    NOT_FOUND = "not_found"
    BAD_REQUEST = "bad_request"
    RATE_LIMITED = "rate_limited"
    INTERNAL_ERROR = "internal_error"
    VALIDATION_ERROR = "validation_error"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"


class APIError(BaseModel):
    """Standard error response body returned by all error handlers.

    Attributes:
        code: Machine-readable error code from ErrorCode enum.
        message: Human-readable error description.
        details: Optional structured details (e.g. field-level validation errors).
        request_id: Optional request identifier for debugging.
    """

    code: ErrorCode
    message: str
    details: dict | None = None
    request_id: str | None = None


# ─── Helper factories ─────────────────────────────────────────────────────────


def not_found(message: str = "Resource not found", *, request_id: str | None = None) -> APIError:
    return APIError(code=ErrorCode.NOT_FOUND, message=message, request_id=request_id)


def bad_request(
    message: str = "Bad request",
    *,
    details: dict | None = None,
    request_id: str | None = None,
) -> APIError:
    return APIError(code=ErrorCode.BAD_REQUEST, message=message, details=details, request_id=request_id)


def rate_limited(message: str = "Rate limit exceeded", *, request_id: str | None = None) -> APIError:
    return APIError(code=ErrorCode.RATE_LIMITED, message=message, request_id=request_id)


def internal_error(message: str = "Internal server error", *, request_id: str | None = None) -> APIError:
    return APIError(code=ErrorCode.INTERNAL_ERROR, message=message, request_id=request_id)


# ─── FastAPI exception handler registration ────────────────────────────────────


def register_error_handlers(app):
    """Register structured JSON error handlers on a FastAPI app."""
    from fastapi import Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse
    from starlette.exceptions import HTTPException as StarletteHTTPException

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        rid = getattr(request.state, "request_id", None)
        if exc.status_code == 404:
            err = not_found(request_id=rid)
        elif exc.status_code == 403:
            err = APIError(code=ErrorCode.FORBIDDEN, message=str(exc.detail), request_id=rid)
        elif exc.status_code == 429:
            err = rate_limited(request_id=rid)
        else:
            err = APIError(code=ErrorCode.INTERNAL_ERROR, message=str(exc.detail), request_id=rid)
        return JSONResponse(
            status_code=exc.status_code,
            content=err.model_dump(),
            headers={"X-Request-ID": rid} if rid else {},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        rid = getattr(request.state, "request_id", None)
        err = APIError(
            code=ErrorCode.VALIDATION_ERROR,
            message="Request validation failed",
            details={"errors": exc.errors()},
            request_id=rid,
        )
        return JSONResponse(status_code=422, content=err.model_dump())

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        rid = getattr(request.state, "request_id", None)
        err = internal_error(request_id=rid)
        return JSONResponse(status_code=500, content=err.model_dump())
