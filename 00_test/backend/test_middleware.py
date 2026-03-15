"""Unit tests for middleware (02_backend/app/core/middleware.py).

Tests exception handlers by loading the module with mocked deps, then calling
the handler functions directly with mock Request objects.

Test IDs: MW-001 to MW-004
"""

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------

BACKEND_ROOT = Path(__file__).parent.parent.parent / "02_backend"


def _load_exceptions():
    """Load the exceptions module (pure Python, no deps)."""
    mod_path = BACKEND_ROOT / "app" / "core" / "exceptions.py"
    spec = importlib.util.spec_from_file_location("exceptions", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_middleware(exc_module):
    """Load middleware module with mocked app-level imports."""
    mod_path = BACKEND_ROOT / "app" / "core" / "middleware.py"
    spec = importlib.util.spec_from_file_location("middleware", mod_path)
    mod = importlib.util.module_from_spec(spec)

    # Build mock for app.core.exceptions that contains the real classes
    exc_mock = MagicMock()
    exc_mock.AppException = exc_module.AppException
    exc_mock.NotFoundError = exc_module.NotFoundError
    exc_mock.UnauthorizedError = exc_module.UnauthorizedError
    exc_mock.ForbiddenError = exc_module.ForbiddenError

    logging_mock = MagicMock(
        get_logger=MagicMock(return_value=MagicMock()),
        request_id_ctx=MagicMock(),
    )

    mocked = {
        "app.core.exceptions": exc_mock,
        "app.core.logging": logging_mock,
        "fastapi": MagicMock(),
        "fastapi.responses": MagicMock(),
        "starlette.middleware.base": MagicMock(),
    }

    # We need JSONResponse to actually work so we can inspect status_code
    # Use a minimal stand-in that captures constructor args.
    class FakeJSONResponse:
        def __init__(self, status_code, content):
            self.status_code = status_code
            self.content = content

    with patch.dict("sys.modules", mocked):
        # Patch JSONResponse in the module namespace after load
        import builtins
        spec.loader.exec_module(mod)

    # Replace the JSONResponse reference inside the loaded module
    mod.JSONResponse = FakeJSONResponse

    # Re-bind the exception map using real exception classes (because the
    # module-level _EXCEPTION_STATUS_MAP was built at load time with the
    # real classes from our exc_mock).
    # Verify the map is populated correctly:
    assert exc_module.NotFoundError in mod._EXCEPTION_STATUS_MAP
    assert exc_module.ForbiddenError in mod._EXCEPTION_STATUS_MAP

    return mod


# Load once at module level
exc_mod = _load_exceptions()
mw_mod = _load_middleware(exc_mod)

AppException = exc_mod.AppException
NotFoundError = exc_mod.NotFoundError
UnauthorizedError = exc_mod.UnauthorizedError
ForbiddenError = exc_mod.ForbiddenError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_request(request_id="test-req-id"):
    """Create a mock Request with state.request_id."""
    mock_request = MagicMock()
    mock_request.state.request_id = request_id
    return mock_request


# ===================================================================
# app_exception_handler  (MW-001 to MW-003)
# ===================================================================

class TestAppExceptionHandler:
    """MW-001 to MW-003: app_exception_handler maps exceptions to HTTP codes."""

    @pytest.mark.asyncio
    async def test_mw001_app_exception_returns_400(self):
        """MW-001: Generic AppException maps to 400."""
        request = _make_mock_request()
        exc = AppException("something wrong", code="BAD_REQUEST")

        response = await mw_mod.app_exception_handler(request, exc)

        assert response.status_code == 400
        assert response.content["detail"] == "something wrong"
        assert response.content["code"] == "BAD_REQUEST"
        assert response.content["request_id"] == "test-req-id"

    @pytest.mark.asyncio
    async def test_mw002_not_found_returns_404(self):
        """MW-002: NotFoundError maps to 404."""
        request = _make_mock_request("req-42")
        exc = NotFoundError("Job", "job-42")

        response = await mw_mod.app_exception_handler(request, exc)

        assert response.status_code == 404
        assert response.content["code"] == "NOT_FOUND"
        assert "job-42" in response.content["detail"]
        assert response.content["request_id"] == "req-42"

    @pytest.mark.asyncio
    async def test_mw003_forbidden_returns_403(self):
        """MW-003: ForbiddenError maps to 403."""
        request = _make_mock_request()
        exc = ForbiddenError("Access denied")

        response = await mw_mod.app_exception_handler(request, exc)

        assert response.status_code == 403
        assert response.content["code"] == "FORBIDDEN"
        assert response.content["detail"] == "Access denied"


# ===================================================================
# unhandled_exception_handler  (MW-004)
# ===================================================================

class TestUnhandledExceptionHandler:
    """MW-004: unhandled_exception_handler returns 500."""

    @pytest.mark.asyncio
    async def test_mw004_unhandled_returns_500(self):
        """MW-004: Any unhandled exception maps to 500 with generic message."""
        request = _make_mock_request("req-err")
        exc = RuntimeError("kaboom")

        response = await mw_mod.unhandled_exception_handler(request, exc)

        assert response.status_code == 500
        assert response.content["code"] == "INTERNAL_ERROR"
        assert response.content["detail"] == "Internal server error"
        assert response.content["request_id"] == "req-err"
