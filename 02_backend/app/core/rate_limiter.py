# In-memory rate limiter (token bucket, single-instance Phase 1)

import time
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class TokenBucket:
    """Simple token bucket for rate limiting."""

    __slots__ = ("limit", "window", "tokens", "last_refill")

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self.tokens = float(limit)
        self.last_refill = time.monotonic()

    def consume(self) -> tuple[bool, int, float]:
        """Try to consume a token. Returns (allowed, remaining, reset_seconds)."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        # Refill tokens based on elapsed time
        self.tokens = min(self.limit, self.tokens + elapsed * (self.limit / self.window))
        self.last_refill = now

        if self.tokens >= 1:
            self.tokens -= 1
            return True, int(self.tokens), self.window - elapsed % self.window
        else:
            return False, 0, self.window - elapsed % self.window


class RateLimiter:
    """In-memory rate limiter with per-key token buckets."""

    def __init__(self):
        self._buckets: dict[str, TokenBucket] = {}

    def check(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int, float]:
        """Check rate limit for key. Returns (allowed, remaining, reset_seconds)."""
        bucket_key = f"{key}:{limit}:{window_seconds}"
        if bucket_key not in self._buckets:
            self._buckets[bucket_key] = TokenBucket(limit, window_seconds)
        return self._buckets[bucket_key].consume()


# Route-specific rate limits: (max_requests, window_seconds)
RATE_LIMITS: dict[str, tuple[int, int]] = {
    "/api/v1/upload": (10, 60),
    "/api/v1/auth/login": (5, 60),
    "/api/v1/auth/register": (3, 60),
}
DEFAULT_RATE_LIMIT = (60, 60)

# Paths excluded from rate limiting
EXCLUDED_PREFIXES = ("/api/v1/internal/", "/health")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply rate limiting per IP address."""

    def __init__(self, app, rate_limiter: RateLimiter = None):
        super().__init__(app)
        self.limiter = rate_limiter or RateLimiter()

    async def dispatch(self, request: Request, call_next):
        if not settings.rate_limit_enabled:
            return await call_next(request)

        path = request.url.path

        # Skip internal endpoints and health
        for prefix in EXCLUDED_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Determine rate limit for this path
        limit, window = DEFAULT_RATE_LIMIT
        for route_prefix, (route_limit, route_window) in RATE_LIMITS.items():
            if path.startswith(route_prefix):
                limit, window = route_limit, route_window
                break

        # Use client IP as key
        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{path}"

        allowed, remaining, reset = self.limiter.check(key, limit, window)

        if not allowed:
            logger.warning(
                "Rate limit exceeded: ip=%s path=%s limit=%d/%ds",
                client_ip, path, limit, window,
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests, please slow down"},
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(reset)),
                    "Retry-After": str(int(reset)),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(reset))
        return response
