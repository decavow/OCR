"""Tests for token hashing (hash_token in auth/utils.py).

Ensures session tokens are hashed consistently and securely.

Test IDs: TH-001 to TH-004
"""

import hashlib
import importlib.util
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).parent.parent.parent / "02_backend"


def _load_hash_token():
    """Load hash_token from auth/utils.py (requires bcrypt installed)."""
    mod_path = BACKEND_ROOT / "app" / "modules" / "auth" / "utils.py"
    spec = importlib.util.spec_from_file_location("auth_utils_th", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.hash_token


hash_token = _load_hash_token()


class TestTokenHashing:
    def test_th001_hash_is_sha256_hex(self):
        """TH-001: hash_token produces a 64-char hex SHA-256 digest."""
        token = "test-token-abc123"
        result = hash_token(token)
        expected = hashlib.sha256(token.encode()).hexdigest()
        assert result == expected
        assert len(result) == 64

    def test_th002_same_input_same_hash(self):
        """TH-002: Same token always produces the same hash."""
        token = "my-session-token"
        assert hash_token(token) == hash_token(token)

    def test_th003_different_input_different_hash(self):
        """TH-003: Different tokens produce different hashes."""
        assert hash_token("token-a") != hash_token("token-b")

    def test_th004_hash_not_equal_to_input(self):
        """TH-004: Hash output is never equal to the raw input."""
        token = "some-token"
        assert hash_token(token) != token
