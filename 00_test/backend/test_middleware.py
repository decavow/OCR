"""
Test cases for Core Middleware (MW-001 to MW-004)

Covers:
- RequestLoggingMiddleware logs method, path, status
- app_exception_handler maps AppException -> correct status code
- NotFoundError -> 404
- Unhandled exception -> 500
"""

import pytest
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch


# Load exceptions module
exc_path = Path(__file__).parent.parent.parent / "02_backend" / "app" / "core" / "exceptions.py"
spec_exc = importlib.util.spec_from_file_location("exceptions", exc_path)
exc_mod = importlib.util.module_from_spec(spec_exc)
spec_exc.loader.exec_module(exc_mod)

AppException = exc_mod.AppException
NotFoundError = exc_mod.NotFoundError
UnauthorizedError = exc_mod.UnauthorizedError
ForbiddenError = exc_mod.ForbiddenError


@pytest.fixture
def middleware_module():
    """Load middleware module with mocked dependencies."""
    logger_mock = MagicMock()
    mocked_modules = {
        "app.core.logging": MagicMock(get_logger=MagicMock(return_value=logger_mock)),
        "app.core.exceptions": exc_mod,
        "app.core.rate_limiter": MagicMock(),
    }
    with patch.dict("sys.modules", mocked_modules):
        mod_path = Path(__file__).parent.parent.parent / "02_backend" / "app" / "core" / "middleware.py"
        spec = importlib.util.spec_from_file_location("middleware", mod_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod._logger = logger_mock
        yield mod, logger_mock


def make_request_mock(method="GET", path="/api/v1/test", request_id=None):
    """Create a mock Starlette Request."""
    req = MagicMock()
    req.method = method
    req.url.path = path
    req.headers.get = MagicMock(return_value=request_id)
    req.state = MagicMock()
    if request_id:
        req.state.request_id = request_id
    else:
        req.state.request_id = None
    return req


class TestAppExceptionHandler:
    """MW-002, MW-003: app_exception_handler maps exceptions to correct status codes."""

    @pytest.mark.asyncio
    async def test_not_found_error_returns_404(self, middleware_module):
        """MW-003: NotFoundError -> 404."""
        mod, _ = middleware_module
        request = make_request_mock()
        exc = NotFoundError("Job", "abc-123")

        response = await mod.app_exception_handler(request, exc)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_unauthorized_error_returns_401(self, middleware_module):
        mod, _ = middleware_module
        request = make_request_mock()
        exc = UnauthorizedError("Token expired")

        response = await mod.app_exception_handler(request, exc)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_forbidden_error_returns_403(self, middleware_module):
        mod, _ = middleware_module
        request = make_request_mock()
        exc = ForbiddenError("Access denied")

        response = await mod.app_exception_handler(request, exc)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_generic_app_exception_returns_400(self, middleware_module):
        """MW-002: Generic AppException defaults to 400."""
        mod, _ = middleware_module
        request = make_request_mock()
        exc = AppException("Something wrong", code="BAD_INPUT")

        response = await mod.app_exception_handler(request, exc)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_response_contains_error_detail(self, middleware_module):
        mod, _ = middleware_module
        request = make_request_mock()
        exc = NotFoundError("Job", "xyz")

        response = await mod.app_exception_handler(request, exc)
        import json
        body = json.loads(response.body.decode())
        assert "detail" in body
        assert body["code"] == "NOT_FOUND"


class TestUnhandledExceptionHandler:
    """MW-004: Unhandled exception -> 500."""

    @pytest.mark.asyncio
    async def test_returns_500(self, middleware_module):
        mod, _ = middleware_module
        request = make_request_mock()
        exc = RuntimeError("Unexpected crash")

        response = await mod.unhandled_exception_handler(request, exc)
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_response_hides_internal_details(self, middleware_module):
        mod, _ = middleware_module
        request = make_request_mock()
        exc = RuntimeError("secret database password")

        response = await mod.unhandled_exception_handler(request, exc)
        import json
        body = json.loads(response.body.decode())
        assert body["detail"] == "Internal server error"
        assert body["code"] == "INTERNAL_ERROR"
        # Should NOT leak the actual error message
        assert "secret" not in body["detail"]
