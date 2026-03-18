"""Tests for config.py secret_key validation logic.

Tests the validate_secret_key method ensuring:
- Insecure default keys emit critical warnings
- Short keys emit warnings
- Strong keys pass silently

Test IDs: CFG-001 to CFG-006
"""

import warnings
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

BACKEND_ROOT = Path(__file__).parent.parent.parent / "02_backend"


def _load_config_module():
    """Load config.py with mocked pydantic_settings."""
    mod_path = BACKEND_ROOT / "app" / "config.py"
    spec = importlib.util.spec_from_file_location("app.config_test", mod_path)
    mod = importlib.util.module_from_spec(spec)

    # Mock pydantic_settings so we can import the module
    mock_base_settings = type("BaseSettings", (), {
        "__init_subclass__": classmethod(lambda cls, **kw: None),
        "Config": type("Config", (), {}),
    })

    mock_ps = MagicMock()
    mock_ps.BaseSettings = mock_base_settings

    with patch.dict("sys.modules", {"pydantic_settings": mock_ps}):
        spec.loader.exec_module(mod)

    return mod


class TestSecretKeyValidation:
    """Test validate_secret_key method on Settings."""

    def _make_settings(self, config_mod, secret_key: str):
        s = config_mod.Settings()
        s.secret_key = secret_key
        return s

    def test_cfg001_insecure_default_key_emits_warning(self):
        config_mod = _load_config_module()
        s = self._make_settings(config_mod, "your-secret-key-change-in-production")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            s.validate_secret_key()
            assert len(w) == 1
            assert "insecure default" in str(w[0].message).lower()

    def test_cfg002_empty_key_emits_warning(self):
        config_mod = _load_config_module()
        s = self._make_settings(config_mod, "")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            s.validate_secret_key()
            assert len(w) == 1
            assert "insecure default" in str(w[0].message).lower()

    def test_cfg003_short_key_emits_warning(self):
        config_mod = _load_config_module()
        s = self._make_settings(config_mod, "short-key-15chars")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            s.validate_secret_key()
            assert len(w) == 1
            assert "too short" in str(w[0].message).lower()

    def test_cfg004_strong_key_no_warning(self):
        config_mod = _load_config_module()
        s = self._make_settings(config_mod, "a" * 64)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            s.validate_secret_key()
            assert len(w) == 0

    def test_cfg005_32_char_key_no_warning(self):
        config_mod = _load_config_module()
        s = self._make_settings(config_mod, "x" * 32)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            s.validate_secret_key()
            assert len(w) == 0

    def test_cfg006_known_weak_keys_all_flagged(self):
        config_mod = _load_config_module()
        weak_keys = [
            "your-secret-key-change-in-production",
            "dev-secret-key-change-in-production",
            "changeme",
            "secret",
        ]
        for key in weak_keys:
            s = self._make_settings(config_mod, key)
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                s.validate_secret_key()
                assert len(w) == 1, f"Expected warning for key: {key}"
