"""Unit tests for RateLimiter (02_backend/app/core/rate_limiter.py).

Tests TokenBucket, RateLimiter, and configuration constants.
Requires mocked app deps (app.config, app.core.logging).

Test IDs: RL-001 to RL-010
"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module loader — mock app deps so the module can be imported
# ---------------------------------------------------------------------------

BACKEND_ROOT = Path(__file__).parent.parent.parent / "02_backend"


def _load():
    mod_path = BACKEND_ROOT / "app" / "core" / "rate_limiter.py"
    spec = importlib.util.spec_from_file_location("rate_limiter", mod_path)
    mod = importlib.util.module_from_spec(spec)
    mocked = {
        "fastapi": MagicMock(),
        "fastapi.responses": MagicMock(),
        "starlette.middleware.base": MagicMock(),
        "app.core.logging": MagicMock(get_logger=MagicMock(return_value=MagicMock())),
        "app.config": MagicMock(settings=MagicMock()),
    }
    with patch.dict("sys.modules", mocked):
        spec.loader.exec_module(mod)
    return mod


rl = _load()
TokenBucket = rl.TokenBucket
RateLimiter = rl.RateLimiter
RATE_LIMITS = rl.RATE_LIMITS
DEFAULT_RATE_LIMIT = rl.DEFAULT_RATE_LIMIT
EXCLUDED_PREFIXES = rl.EXCLUDED_PREFIXES


# ===================================================================
# TokenBucket  (RL-001 to RL-003)
# ===================================================================


class TestTokenBucket:
    """RL-001 to RL-003: Token bucket consume behaviour."""

    def test_rl001_consume_within_limit(self):
        """RL-001: First consume within limit returns allowed=True."""
        bucket = TokenBucket(limit=5, window_seconds=60)
        allowed, remaining, reset = bucket.consume()
        assert allowed is True
        assert remaining >= 0

    def test_rl002_consume_over_limit(self):
        """RL-002: After exhausting tokens, consume returns allowed=False."""
        bucket = TokenBucket(limit=2, window_seconds=60)
        bucket.consume()
        bucket.consume()
        allowed, remaining, reset = bucket.consume()
        assert allowed is False
        assert remaining == 0

    def test_rl003_remaining_tracks_correctly(self):
        """RL-003: Remaining decrements with each consume."""
        bucket = TokenBucket(limit=5, window_seconds=60)
        _, r1, _ = bucket.consume()
        _, r2, _ = bucket.consume()
        # Each consume should reduce remaining by ~1
        assert r1 > r2


# ===================================================================
# RateLimiter  (RL-004)
# ===================================================================


class TestRateLimiter:
    """RL-004: Per-key independence."""

    def test_rl004_different_keys_independent(self):
        """RL-004: Different keys get independent buckets."""
        limiter = RateLimiter()
        # Exhaust key-A (limit=1)
        limiter.check("key-a", limit=1, window_seconds=60)
        allowed_a, _, _ = limiter.check("key-a", limit=1, window_seconds=60)

        # key-B should still have tokens
        allowed_b, _, _ = limiter.check("key-b", limit=1, window_seconds=60)

        assert allowed_a is False
        assert allowed_b is True


# ===================================================================
# Configuration constants  (RL-005 to RL-010)
# ===================================================================


class TestRateLimitConfig:
    """RL-005 to RL-010: Built-in rate limit constants and exclusions."""

    def test_rl005_upload_limit(self):
        """RL-005: /api/v1/upload limit is 10 per 60s."""
        assert RATE_LIMITS["/api/v1/upload"] == (10, 60)

    def test_rl006_login_limit(self):
        """RL-006: /api/v1/auth/login limit is 5 per 60s."""
        assert RATE_LIMITS["/api/v1/auth/login"] == (5, 60)

    def test_rl007_register_limit(self):
        """RL-007: /api/v1/auth/register limit is 3 per 60s."""
        assert RATE_LIMITS["/api/v1/auth/register"] == (3, 60)

    def test_rl008_default_rate_limit(self):
        """RL-008: Default rate limit is 60 per 60s."""
        assert DEFAULT_RATE_LIMIT == (60, 60)

    def test_rl009_internal_rate_limited(self):
        """RL-009: /api/v1/internal/ has its own higher rate limit (not excluded)."""
        # Internal endpoints should NOT be excluded — they get their own limit
        assert not any(p.startswith("/api/v1/internal") for p in EXCLUDED_PREFIXES)
        assert hasattr(rl, "INTERNAL_RATE_LIMIT")
        limit, window = rl.INTERNAL_RATE_LIMIT
        assert limit > 60  # Higher than default

    def test_rl010_health_excluded(self):
        """RL-010: /health is in excluded prefixes."""
        assert "/health" in EXCLUDED_PREFIXES
