"""
Test cases for Core Exceptions (EX-001 to EX-004)

Covers:
- AppException base class
- NotFoundError (404)
- UnauthorizedError (401)
- ForbiddenError (403)
- ValidationError
- Message preservation
"""

import importlib.util
from pathlib import Path

# Load exceptions module directly
exc_path = Path(__file__).parent.parent.parent / "02_backend" / "app" / "core" / "exceptions.py"
spec = importlib.util.spec_from_file_location("exceptions", exc_path)
exc_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exc_mod)

AppException = exc_mod.AppException
NotFoundError = exc_mod.NotFoundError
UnauthorizedError = exc_mod.UnauthorizedError
ForbiddenError = exc_mod.ForbiddenError
ValidationError = exc_mod.ValidationError


class TestNotFoundError:
    """EX-001: NotFoundError has correct code."""

    def test_code_is_not_found(self):
        exc = NotFoundError("Job", "abc-123")
        assert exc.code == "NOT_FOUND"

    def test_message_contains_resource_and_id(self):
        exc = NotFoundError("Job", "abc-123")
        assert "Job" in exc.message
        assert "abc-123" in exc.message

    def test_inherits_app_exception(self):
        exc = NotFoundError("File", "x")
        assert isinstance(exc, AppException)


class TestUnauthorizedError:
    """EX-002: UnauthorizedError has correct code."""

    def test_code_is_unauthorized(self):
        exc = UnauthorizedError()
        assert exc.code == "UNAUTHORIZED"

    def test_default_message(self):
        exc = UnauthorizedError()
        assert exc.message == "Unauthorized"

    def test_custom_message(self):
        exc = UnauthorizedError("Token expired")
        assert exc.message == "Token expired"


class TestForbiddenError:
    """EX-003: ForbiddenError has correct code."""

    def test_code_is_forbidden(self):
        exc = ForbiddenError()
        assert exc.code == "FORBIDDEN"

    def test_default_message(self):
        exc = ForbiddenError()
        assert exc.message == "Forbidden"

    def test_custom_message(self):
        exc = ForbiddenError("Access denied to resource")
        assert exc.message == "Access denied to resource"


class TestAppException:
    """EX-004: Base AppException preserves message."""

    def test_message_preserved(self):
        exc = AppException("Something went wrong")
        assert exc.message == "Something went wrong"
        assert str(exc) == "Something went wrong"

    def test_code_preserved(self):
        exc = AppException("Error", code="CUSTOM_CODE")
        assert exc.code == "CUSTOM_CODE"

    def test_code_defaults_to_none(self):
        exc = AppException("Error")
        assert exc.code is None

    def test_inherits_exception(self):
        exc = AppException("Error")
        assert isinstance(exc, Exception)


class TestValidationError:
    """Additional: ValidationError has correct code."""

    def test_code_is_validation_error(self):
        exc = ValidationError("Invalid input")
        assert exc.code == "VALIDATION_ERROR"

    def test_message_preserved(self):
        exc = ValidationError("Email format invalid")
        assert exc.message == "Email format invalid"
