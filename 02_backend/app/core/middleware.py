# Error handler, request timing, request logging, correlation ID

import time
import uuid
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import AppException, NotFoundError, UnauthorizedError, ForbiddenError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Map AppException subclasses to HTTP status codes
_EXCEPTION_STATUS_MAP = {
    NotFoundError: 404,
    UnauthorizedError: 401,
    ForbiddenError: 403,
}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log request timing, correlation ID, and details."""

    async def dispatch(self, request: Request, call_next):
        # Generate or reuse correlation ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        start_time = time.time()

        response = await call_next(request)

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"{request.method} {request.url.path} - {response.status_code} - {duration_ms:.2f}ms",
            extra={"request_id": request_id},
        )

        response.headers["X-Request-ID"] = request_id
        return response


async def app_exception_handler(request: Request, exc: AppException):
    """Handle application exceptions with proper status codes."""
    request_id = getattr(request.state, "request_id", None)
    status_code = _EXCEPTION_STATUS_MAP.get(type(exc), 400)

    logger.warning(
        f"AppException: {exc.code} - {exc.message}",
        extra={"request_id": request_id, "status_code": status_code},
    )

    return JSONResponse(
        status_code=status_code,
        content={"detail": exc.message, "code": exc.code, "request_id": request_id},
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions."""
    request_id = getattr(request.state, "request_id", None)

    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True,
        extra={"request_id": request_id},
    )

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "code": "INTERNAL_ERROR", "request_id": request_id},
    )


def setup_middleware(app: FastAPI) -> None:
    """Setup all middleware."""
    from app.core.rate_limiter import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
