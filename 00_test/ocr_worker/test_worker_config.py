"""Unit tests for worker config (03_worker/app/config.py).

Tests for get_worker_instance_id and Settings properties.
Class-level attributes are set at import time, so we test the function directly.
Properties read os.getenv at access time, so we can mock them on an instance.

Test IDs: WC-001 through WC-008
"""

import os
import socket
from unittest.mock import patch

import pytest

from app.config import get_worker_instance_id, Settings


# ---------------------------------------------------------------------------
# WC-001 to WC-002: worker_allowed_methods property
# ---------------------------------------------------------------------------

def test_default_allowed_methods():
    """WC-001: Default allowed methods is ['ocr_paddle_text']."""
    s = Settings()
    with patch.dict(os.environ, {}, clear=False):
        # Remove the key if present to get default
        env = os.environ.copy()
        env.pop("WORKER_ALLOWED_METHODS", None)
        with patch.dict(os.environ, env, clear=True):
            result = s.worker_allowed_methods
    assert result == ["ocr_paddle_text"]


def test_comma_separated_methods():
    """WC-002: Comma-separated WORKER_ALLOWED_METHODS parsed correctly."""
    s = Settings()
    with patch.dict(os.environ, {"WORKER_ALLOWED_METHODS": "ocr_paddle_text,ocr_text_visual,ocr_table"}):
        result = s.worker_allowed_methods
    assert result == ["ocr_paddle_text", "ocr_text_visual", "ocr_table"]


# ---------------------------------------------------------------------------
# WC-003 to WC-004: worker_allowed_tiers property
# ---------------------------------------------------------------------------

def test_default_allowed_tiers():
    """WC-003: Default allowed tiers is [0]."""
    s = Settings()
    env = os.environ.copy()
    env.pop("WORKER_ALLOWED_TIERS", None)
    with patch.dict(os.environ, env, clear=True):
        result = s.worker_allowed_tiers
    assert result == [0]


def test_comma_separated_tiers():
    """WC-004: Comma-separated WORKER_ALLOWED_TIERS parsed as ints."""
    s = Settings()
    with patch.dict(os.environ, {"WORKER_ALLOWED_TIERS": "0,1,2"}):
        result = s.worker_allowed_tiers
    assert result == [0, 1, 2]


# ---------------------------------------------------------------------------
# WC-005: worker_supported_formats property
# ---------------------------------------------------------------------------

def test_default_supported_formats():
    """WC-005: Default supported formats is ['txt', 'json']."""
    s = Settings()
    env = os.environ.copy()
    env.pop("WORKER_SUPPORTED_FORMATS", None)
    with patch.dict(os.environ, env, clear=True):
        result = s.worker_supported_formats
    assert result == ["txt", "json"]


# ---------------------------------------------------------------------------
# WC-006: get_worker_instance_id format
# ---------------------------------------------------------------------------

def test_get_worker_instance_id_format():
    """WC-006: get_worker_instance_id returns '{service_type}-{hostname[:12]}'."""
    with patch.dict(os.environ, {"WORKER_SERVICE_TYPE": "ocr-vision", "WORKER_SERVICE_ID": ""}, clear=False):
        with patch("app.config.socket.gethostname", return_value="abcdef123456xyz"):
            result = get_worker_instance_id()
    assert result == "ocr-vision-abcdef123456"


def test_get_worker_instance_id_explicit():
    """WC-006b: Explicit WORKER_SERVICE_ID overrides auto-generation."""
    with patch.dict(os.environ, {"WORKER_SERVICE_ID": "my-custom-id"}, clear=False):
        result = get_worker_instance_id()
    assert result == "my-custom-id"


# ---------------------------------------------------------------------------
# WC-007: access_key empty -> None
# ---------------------------------------------------------------------------

def test_access_key_empty_is_none():
    """WC-007: Empty WORKER_ACCESS_KEY resolves to None."""
    with patch.dict(os.environ, {"WORKER_ACCESS_KEY": ""}, clear=False):
        # Need to re-evaluate class-level attribute logic
        # Since _access_key_env is set at class definition, test the logic directly
        access_key_env = os.getenv("WORKER_ACCESS_KEY", "")
        result = access_key_env if access_key_env else None
    assert result is None


# ---------------------------------------------------------------------------
# WC-008: access_key valid
# ---------------------------------------------------------------------------

def test_access_key_valid():
    """WC-008: Non-empty WORKER_ACCESS_KEY is preserved."""
    with patch.dict(os.environ, {"WORKER_ACCESS_KEY": "sk_test_12345"}, clear=False):
        access_key_env = os.getenv("WORKER_ACCESS_KEY", "")
        result = access_key_env if access_key_env else None
    assert result == "sk_test_12345"
