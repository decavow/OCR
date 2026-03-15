"""Unit tests for exception hierarchy (02_backend/app/core/exceptions.py).

Pure logic tests — no external dependencies.

Test IDs: EX-001 to EX-004
"""

import importlib.util
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------

BACKEND_ROOT = Path(__file__).parent.parent.parent / "02_backend"


def _load():
    mod_path = BACKEND_ROOT / "app" / "core" / "exceptions.py"
    spec = importlib.util.spec_from_file_location("exceptions", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


exc = _load()
AppException = exc.AppException
NotFoundError = exc.NotFoundError
ValidationError = exc.ValidationError
UnauthorizedError = exc.UnauthorizedError
ForbiddenError = exc.ForbiddenError


# ===================================================================
# Exception attributes  (EX-001 to EX-004)
# ===================================================================


class TestExceptions:
    """EX-001 to EX-004: Exception classes carry correct code and message."""

    def test_ex001_not_found_error(self):
        """EX-001: NotFoundError has code='NOT_FOUND' and formatted message."""
        err = NotFoundError("Job", "job-42")
        assert err.code == "NOT_FOUND"
        assert err.message == "Job job-42 not found"
        assert isinstance(err, AppException)

    def test_ex002_unauthorized_error(self):
        """EX-002: UnauthorizedError has code='UNAUTHORIZED' and default message."""
        err = UnauthorizedError()
        assert err.code == "UNAUTHORIZED"
        assert err.message == "Unauthorized"
        assert isinstance(err, AppException)

    def test_ex003_forbidden_error(self):
        """EX-003: ForbiddenError has code='FORBIDDEN' and default message."""
        err = ForbiddenError()
        assert err.code == "FORBIDDEN"
        assert err.message == "Forbidden"
        assert isinstance(err, AppException)

    def test_ex004_app_exception_message_preserved(self):
        """EX-004: AppException preserves custom message and code."""
        err = AppException("something broke", code="CUSTOM")
        assert err.message == "something broke"
        assert err.code == "CUSTOM"
        assert str(err) == "something broke"
