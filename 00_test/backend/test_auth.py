"""Unit tests for AuthService (02_backend/app/modules/auth/service.py).

Service-level tests with mocked repositories. Tests register, login, logout,
and validate_session methods.

Test IDs: AU-001 to AU-010
"""

import importlib.util
import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------

BACKEND_ROOT = Path(__file__).parent.parent.parent / "02_backend"


def _load_auth_exceptions():
    """Load auth exceptions with real base exception classes."""
    # Load core exceptions (pure Python, no deps)
    exc_path = BACKEND_ROOT / "app" / "core" / "exceptions.py"
    spec = importlib.util.spec_from_file_location("core_exceptions_au", exc_path)
    exc_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exc_mod)

    # Load auth exceptions with core exceptions available
    auth_exc_path = BACKEND_ROOT / "app" / "modules" / "auth" / "exceptions.py"
    spec2 = importlib.util.spec_from_file_location("auth_exceptions_au", auth_exc_path)
    mod2 = importlib.util.module_from_spec(spec2)

    mocked = {
        "app.core.exceptions": exc_mod,
    }
    with patch.dict("sys.modules", mocked):
        spec2.loader.exec_module(mod2)
    return exc_mod, mod2


def _load_auth_service(auth_exc_mod):
    """Load AuthService with mocked repos, mocked bcrypt utils."""
    mod_path = BACKEND_ROOT / "app" / "modules" / "auth" / "service.py"
    spec = importlib.util.spec_from_file_location("auth_service_au", mod_path)
    mod = importlib.util.module_from_spec(spec)

    # Create simple hash/verify functions that don't need bcrypt
    def fake_hash_password(password):
        return "hashed:" + hashlib.sha256(password.encode()).hexdigest()

    def fake_verify_password(password, hashed):
        return hashed == "hashed:" + hashlib.sha256(password.encode()).hexdigest()

    # Build a utils mock with our fake functions
    utils_mock_module = MagicMock()
    utils_mock_module.hash_password = fake_hash_password
    utils_mock_module.verify_password = fake_verify_password

    # Auth exceptions module namespace
    auth_exc_ns = MagicMock()
    auth_exc_ns.InvalidCredentials = auth_exc_mod.InvalidCredentials
    auth_exc_ns.UserAlreadyExists = auth_exc_mod.UserAlreadyExists
    auth_exc_ns.UserNotFound = auth_exc_mod.UserNotFound

    # Build parent package mock so relative imports resolve
    parent_pkg = MagicMock()
    parent_pkg.utils = utils_mock_module
    parent_pkg.exceptions = auth_exc_ns

    mocked = {
        "app": MagicMock(),
        "app.modules": MagicMock(),
        "app.modules.auth": parent_pkg,
        "app.infrastructure.database.models": MagicMock(),
        "app.infrastructure.database.repositories": MagicMock(),
        "app.config": MagicMock(settings=MagicMock(session_expire_hours=24)),
        "app.modules.auth.utils": utils_mock_module,
        "app.modules.auth.exceptions": auth_exc_ns,
        "sqlalchemy": MagicMock(),
        "sqlalchemy.orm": MagicMock(),
    }

    # Set __package__ so relative imports work
    mod.__package__ = "app.modules.auth"

    with patch.dict("sys.modules", mocked):
        spec.loader.exec_module(mod)

    # Attach our fake functions so tests can use them
    mod._fake_hash_password = fake_hash_password
    mod._fake_verify_password = fake_verify_password

    return mod


# Load modules
core_exc_mod, auth_exc_mod = _load_auth_exceptions()
auth_svc_mod = _load_auth_service(auth_exc_mod)

AuthService = auth_svc_mod.AuthService
InvalidCredentials = auth_exc_mod.InvalidCredentials
UserAlreadyExists = auth_exc_mod.UserAlreadyExists
UserNotFound = auth_exc_mod.UserNotFound
fake_hash = auth_svc_mod._fake_hash_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(user_id="user-1", email="test@test.com", password="password123", deleted_at=None):
    """Create a mock user with hashed password."""
    hashed = fake_hash(password)
    return SimpleNamespace(
        id=user_id,
        email=email,
        password_hash=hashed,
        deleted_at=deleted_at,
    )


def _make_session(session_id="sess-1", user_id="user-1", token="valid-token"):
    return SimpleNamespace(
        id=session_id,
        user_id=user_id,
        token=token,
    )


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def svc():
    """Create AuthService with mocked repos."""
    db = MagicMock()
    service = AuthService(db)
    service.user_repo = MagicMock()
    service.session_repo = MagicMock()
    return service


# ===================================================================
# register  (AU-001 to AU-002)
# ===================================================================

class TestRegister:
    """AU-001 to AU-002: User registration."""

    def test_au001_register_valid_returns_user(self, svc):
        """AU-001: Register with new email creates and returns user."""
        svc.user_repo.get_by_email.return_value = None
        created_user = _make_user(email="new@test.com")
        svc.user_repo.create_user.return_value = created_user

        result = svc.register("new@test.com", "securepass")

        assert result is created_user
        svc.user_repo.get_by_email.assert_called_once_with("new@test.com")
        svc.user_repo.create_user.assert_called_once()
        # Verify password was hashed (second arg should not be plaintext)
        call_args = svc.user_repo.create_user.call_args
        assert call_args[0][0] == "new@test.com"
        assert call_args[0][1] != "securepass"  # Should be hashed
        assert call_args[0][1].startswith("hashed:")  # Our fake hash format

    def test_au002_register_duplicate_raises(self, svc):
        """AU-002: Register with existing email raises UserAlreadyExists."""
        svc.user_repo.get_by_email.return_value = _make_user(email="exists@test.com")

        with pytest.raises(UserAlreadyExists) as exc_info:
            svc.register("exists@test.com", "password")

        assert "exists@test.com" in str(exc_info.value)
        svc.user_repo.create_user.assert_not_called()


# ===================================================================
# login  (AU-003 to AU-005)
# ===================================================================

class TestLogin:
    """AU-003 to AU-005: User login."""

    def test_au003_login_valid_credentials(self, svc):
        """AU-003: Login with correct email+password returns (user, session, raw_token)."""
        user = _make_user(email="user@test.com", password="correctpass")
        session = _make_session(user_id=user.id)
        svc.user_repo.get_by_email.return_value = user
        svc.session_repo.create_session.return_value = session

        result = svc.login("user@test.com", "correctpass")

        assert result[0] is user
        assert result[1] is session
        assert isinstance(result[2], str)  # raw_token returned
        assert len(result[2]) > 0
        svc.session_repo.create_session.assert_called_once()

    def test_au004_login_wrong_password_raises(self, svc):
        """AU-004: Login with wrong password raises InvalidCredentials."""
        user = _make_user(email="user@test.com", password="correctpass")
        svc.user_repo.get_by_email.return_value = user

        with pytest.raises(InvalidCredentials):
            svc.login("user@test.com", "wrongpass")

        svc.session_repo.create_session.assert_not_called()

    def test_au005_login_nonexistent_user_raises(self, svc):
        """AU-005: Login with non-existent email raises InvalidCredentials."""
        svc.user_repo.get_by_email.return_value = None

        with pytest.raises(InvalidCredentials):
            svc.login("nobody@test.com", "anypass")


# ===================================================================
# logout  (AU-006 to AU-007)
# ===================================================================

class TestLogout:
    """AU-006 to AU-007: User logout."""

    def test_au006_logout_valid_token(self, svc):
        """AU-006: Logout with valid token deletes session and returns True."""
        session = _make_session(token="valid-token")
        svc.session_repo.get_valid.return_value = session

        result = svc.logout("valid-token")

        assert result is True
        svc.session_repo.delete.assert_called_once_with(session)

    def test_au007_logout_invalid_token(self, svc):
        """AU-007: Logout with invalid token returns False gracefully."""
        svc.session_repo.get_valid.return_value = None

        result = svc.logout("invalid-token")

        assert result is False
        svc.session_repo.delete.assert_not_called()


# ===================================================================
# validate_session  (AU-008 to AU-010)
# ===================================================================

class TestValidateSession:
    """AU-008 to AU-010: Session validation."""

    def test_au008_validate_valid_session(self, svc):
        """AU-008: Valid session returns the user."""
        session = _make_session(user_id="user-1", token="valid-token")
        user = _make_user(user_id="user-1")
        svc.session_repo.get_valid.return_value = session
        svc.user_repo.get.return_value = user

        result = svc.validate_session("valid-token")

        assert result is user

    def test_au009_validate_expired_session(self, svc):
        """AU-009: Expired session (get_valid returns None) returns None."""
        svc.session_repo.get_valid.return_value = None

        result = svc.validate_session("expired-token")

        assert result is None

    def test_au010_validate_invalid_token(self, svc):
        """AU-010: Invalid token (no session found) returns None."""
        svc.session_repo.get_valid.return_value = None

        result = svc.validate_session("nonexistent-token")

        assert result is None


# ===================================================================
# Edge cases: validate_session with deleted user
# ===================================================================

class TestValidateSessionEdgeCases:
    """Additional edge cases for validate_session."""

    def test_au008b_validate_session_deleted_user_returns_none(self, svc):
        """AU-008b: Valid session but user is soft-deleted returns None."""
        from datetime import datetime, timezone
        session = _make_session(user_id="user-1", token="valid-token")
        user = _make_user(user_id="user-1", deleted_at=datetime.now(timezone.utc))
        svc.session_repo.get_valid.return_value = session
        svc.user_repo.get.return_value = user

        result = svc.validate_session("valid-token")

        assert result is None

    def test_au008c_validate_session_user_not_found_returns_none(self, svc):
        """AU-008c: Valid session but user no longer exists returns None."""
        session = _make_session(user_id="user-gone", token="valid-token")
        svc.session_repo.get_valid.return_value = session
        svc.user_repo.get.return_value = None

        result = svc.validate_session("valid-token")

        assert result is None
