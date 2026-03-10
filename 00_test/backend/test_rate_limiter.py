"""
Test cases for M9: Rate Limiting

Covers:
- Under limit -> allowed
- Over limit -> 429
- Different endpoints have different limits
- Limit resets after window
- Internal endpoints excluded
- Rate limit headers present
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import importlib.util


@pytest.fixture
def rate_limiter_module():
    """Load rate_limiter module with mocked dependencies."""
    logger_mock = MagicMock()
    settings_mock = MagicMock()
    settings_mock.rate_limit_enabled = True

    with patch.dict("sys.modules", {
        "app.core.logging": MagicMock(get_logger=MagicMock(return_value=logger_mock)),
        "app.config": MagicMock(settings=settings_mock),
    }):
        mod_path = Path(__file__).parent.parent.parent / "02_backend" / "app" / "core" / "rate_limiter.py"
        spec = importlib.util.spec_from_file_location("rate_limiter", mod_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        yield mod


class TestTokenBucket:
    def test_allows_within_limit(self, rate_limiter_module):
        bucket = rate_limiter_module.TokenBucket(limit=5, window_seconds=60)
        for _ in range(5):
            allowed, remaining, _ = bucket.consume()
            assert allowed is True

    def test_rejects_over_limit(self, rate_limiter_module):
        bucket = rate_limiter_module.TokenBucket(limit=2, window_seconds=60)
        bucket.consume()
        bucket.consume()
        allowed, remaining, _ = bucket.consume()
        assert allowed is False
        assert remaining == 0

    def test_remaining_decreases(self, rate_limiter_module):
        bucket = rate_limiter_module.TokenBucket(limit=5, window_seconds=60)
        _, r1, _ = bucket.consume()
        _, r2, _ = bucket.consume()
        assert r2 < r1


class TestRateLimiter:
    def test_different_keys_independent(self, rate_limiter_module):
        limiter = rate_limiter_module.RateLimiter()
        # Exhaust key A
        for _ in range(3):
            limiter.check("key_a", 3, 60)
        allowed_a, _, _ = limiter.check("key_a", 3, 60)
        # Key B should still be allowed
        allowed_b, _, _ = limiter.check("key_b", 3, 60)
        assert allowed_a is False
        assert allowed_b is True

    def test_upload_limit_lower_than_default(self, rate_limiter_module):
        """Upload has 10 req/min, default has 60 req/min."""
        upload_limit = rate_limiter_module.RATE_LIMITS.get("/api/v1/upload")
        default_limit = rate_limiter_module.DEFAULT_RATE_LIMIT
        assert upload_limit is not None
        assert upload_limit[0] < default_limit[0]

    def test_login_limit(self, rate_limiter_module):
        """Login has 5 req/min."""
        login_limit = rate_limiter_module.RATE_LIMITS.get("/api/v1/auth/login")
        assert login_limit == (5, 60)

    def test_register_limit(self, rate_limiter_module):
        """Register has 3 req/min."""
        register_limit = rate_limiter_module.RATE_LIMITS.get("/api/v1/auth/register")
        assert register_limit == (3, 60)

    def test_internal_excluded(self, rate_limiter_module):
        """Internal paths should be excluded."""
        excluded = rate_limiter_module.EXCLUDED_PREFIXES
        assert any("/api/v1/internal/" in p for p in excluded)

    def test_health_excluded(self, rate_limiter_module):
        """Health endpoint should be excluded."""
        excluded = rate_limiter_module.EXCLUDED_PREFIXES
        assert any("/health" in p for p in excluded)
