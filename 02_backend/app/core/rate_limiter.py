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
    """In-memory rate limiter with per-key token buckets.

    Includes TTL-based cleanup to prevent unbounded memory growth
    from rotating IPs or many unique clients.
    """

    _MAX_BUCKETS = 10_000
    _CLEANUP_INTERVAL = 300  # 5 minutes

    def __init__(self):
        self._buckets: dict[str, TokenBucket] = {}
        self._last_cleanup = time.monotonic()

    def check(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int, float]:
        """Check rate limit for key. Returns (allowed, remaining, reset_seconds)."""
        self._maybe_cleanup()
        bucket_key = f"{key}:{limit}:{window_seconds}"
        if bucket_key not in self._buckets:
            self._buckets[bucket_key] = TokenBucket(limit, window_seconds)
        return self._buckets[bucket_key].consume()

    def _maybe_cleanup(self) -> None:
        """Remove stale buckets periodically to prevent memory leak."""
        now = time.monotonic()
        if now - self._last_cleanup < self._CLEANUP_INTERVAL:
            return
        self._last_cleanup = now

        # Remove buckets that haven't been used for 2x their window
        stale_keys = [
            k for k, b in self._buckets.items()
            if now - b.last_refill > b.window * 2
        ]
        for k in stale_keys:
            del self._buckets[k]

        # Hard cap: if still over limit, remove oldest
        if len(self._buckets) > self._MAX_BUCKETS:
            sorted_keys = sorted(
                self._buckets, key=lambda k: self._buckets[k].last_refill
            )
            for k in sorted_keys[: len(self._buckets) - self._MAX_BUCKETS]:
                del self._buckets[k]

        if stale_keys:
            logger.debug(f"Rate limiter cleanup: removed {len(stale_keys)} stale buckets")


# Route-specific rate limits: (max_requests, window_seconds)
RATE_LIMITS: dict[str, tuple[int, int]] = {
    "/api/v1/upload": (10, 60),
    "/api/v1/auth/login": (5, 60),
    "/api/v1/auth/register": (3, 60),
}
DEFAULT_RATE_LIMIT = (60, 60)

# Internal endpoints get higher rate limits instead of being excluded
INTERNAL_RATE_LIMIT = (300, 60)  # 300 req/min per worker

# Paths excluded from rate limiting (only health)
EXCLUDED_PREFIXES = ("/health",)


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
        if path.startswith("/api/v1/internal/"):
            limit, window = INTERNAL_RATE_LIMIT
        else:
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
