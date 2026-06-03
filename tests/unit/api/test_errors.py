"""Test standardized error response models."""
import pytest
from pydantic import ValidationError

from app.api.v1.errors import APIError, ErrorCode, not_found, bad_request, rate_limited, internal_error


class TestErrorCode:
    def test_enum_values(self):
        assert ErrorCode.NOT_FOUND.value == "not_found"
        assert ErrorCode.BAD_REQUEST.value == "bad_request"
        assert ErrorCode.RATE_LIMITED.value == "rate_limited"
        assert ErrorCode.INTERNAL_ERROR.value == "internal_error"
        assert ErrorCode.VALIDATION_ERROR.value == "validation_error"
        assert ErrorCode.UNAUTHORIZED.value == "unauthorized"
        assert ErrorCode.FORBIDDEN.value == "forbidden"


class TestAPIErrorModel:
    def test_minimal_construction(self):
        err = APIError(code=ErrorCode.NOT_FOUND, message="Not found")
        assert err.code == ErrorCode.NOT_FOUND
        assert err.message == "Not found"
        assert err.details is None
        assert err.request_id is None

    def test_full_construction(self):
        err = APIError(
            code=ErrorCode.BAD_REQUEST,
            message="Invalid input",
            details={"field": "email", "reason": "required"},
            request_id="req-abc-123",
        )
        assert err.code == ErrorCode.BAD_REQUEST
        assert err.message == "Invalid input"
        assert err.details == {"field": "email", "reason": "required"}
        assert err.request_id == "req-abc-123"

    def test_json_serialization(self):
        err = APIError(code=ErrorCode.RATE_LIMITED, message="Too many requests", request_id="req-xyz")
        data = err.model_dump()
        assert data["code"] == "rate_limited"
        assert data["message"] == "Too many requests"
        assert data["request_id"] == "req-xyz"
        assert data["details"] is None

    def test_code_must_be_valid_enum(self):
        with pytest.raises(ValidationError):
            APIError(code="invalid_code", message="x")  # type: ignore[arg-type]


class TestErrorHelpers:
    def test_not_found_default(self):
        err = not_found()
        assert err.code == ErrorCode.NOT_FOUND
        assert err.message == "Resource not found"

    def test_not_found_custom(self):
        err = not_found(message="User not found", request_id="req-1")
        assert err.message == "User not found"
        assert err.request_id == "req-1"

    def test_bad_request_default(self):
        err = bad_request()
        assert err.code == ErrorCode.BAD_REQUEST
        assert err.message == "Bad request"

    def test_bad_request_with_details(self):
        err = bad_request(message="Invalid JSON", details={"parse_error": "line 3"})
        assert err.details == {"parse_error": "line 3"}

    def test_rate_limited_default(self):
        err = rate_limited()
        assert err.code == ErrorCode.RATE_LIMITED
        assert err.message == "Rate limit exceeded"

    def test_rate_limited_custom(self):
        err = rate_limited(message="Too many requests. Retry in 30s.", request_id="req-2")
        assert err.message == "Too many requests. Retry in 30s."
        assert err.request_id == "req-2"

    def test_internal_error_default(self):
        err = internal_error()
        assert err.code == ErrorCode.INTERNAL_ERROR
        assert err.message == "Internal server error"

    def test_internal_error_custom(self):
        err = internal_error(message="Database connection failed", request_id="req-3")
        assert err.message == "Database connection failed"
        assert err.request_id == "req-3"
