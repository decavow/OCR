# Error handler, request timing, request logging

import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import AppException
from app.core.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log request timing and details."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        response = await call_next(request)

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"{request.method} {request.url.path} - {response.status_code} - {duration_ms:.2f}ms"
        )

        return response


async def app_exception_handler(request: Request, exc: AppException):
    """Handle application exceptions."""
    return JSONResponse(
        status_code=400,
        content={"detail": exc.message, "code": exc.code},
    )


def setup_middleware(app: FastAPI) -> None:
    """Setup all middleware."""
    app.add_middleware(RequestLoggingMiddleware)
    app.add_exception_handler(AppException, app_exception_handler)
