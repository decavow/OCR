"""Auth API integration tests — real HTTP endpoints + real SQLite.

Tests the full auth flow through FastAPI TestClient:
register, login, logout, session validation.

Test IDs: IA-001 to IA-010
"""

from datetime import datetime, timezone, timedelta

import pytest

from helpers import register_and_get_token, auth_header


class TestAuthRegister:
    """IA-001 to IA-002: User registration."""

    def test_ia001_register_new_user(self, client):
        """IA-001: Register new user returns token and user info."""
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "new@example.com", "password": "StrongPass1!"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["email"] == "new@example.com"
        assert data["user"]["is_admin"] is False
        assert "expires_at" in data

    def test_ia002_register_duplicate_email(self, client):
        """IA-002: Registering with existing email returns 400."""
        client.post(
            "/api/v1/auth/register",
            json={"email": "dup@example.com", "password": "Pass1234!"},
        )

        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "dup@example.com", "password": "OtherPass!"},
        )
        assert resp.status_code == 400


class TestAuthLogin:
    """IA-003 to IA-005: User login."""

    def test_ia003_login_valid_credentials(self, client):
        """IA-003: Login with correct credentials returns token."""
        # First register
        client.post(
            "/api/v1/auth/register",
            json={"email": "login@example.com", "password": "MyPass123!"},
        )

        # Then login
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "login@example.com", "password": "MyPass123!"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["email"] == "login@example.com"

    def test_ia004_login_wrong_password(self, client):
        """IA-004: Login with wrong password returns 401."""
        client.post(
            "/api/v1/auth/register",
            json={"email": "wrong@example.com", "password": "Correct123"},
        )

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "wrong@example.com", "password": "WrongPass"},
        )
        assert resp.status_code == 401

    def test_ia005_login_nonexistent_email(self, client):
        """IA-005: Login with non-existent email returns 401."""
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "AnyPass"},
        )
        assert resp.status_code == 401


class TestAuthMe:
    """IA-006 to IA-008: Get current user."""

    def test_ia006_me_with_valid_token(self, client):
        """IA-006: GET /me with valid token returns user info."""
        token = register_and_get_token(client, "me@example.com", "Pass1234!")

        resp = client.get("/api/v1/auth/me", headers=auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["email"] == "me@example.com"

    def test_ia007_me_without_token(self, client):
        """IA-007: GET /me without token returns 401."""
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_ia008_me_with_invalid_token(self, client):
        """IA-008: GET /me with bogus token returns 401."""
        resp = client.get(
            "/api/v1/auth/me",
            headers=auth_header("totally_invalid_token"),
        )
        assert resp.status_code == 401


class TestAuthLogout:
    """IA-009: Logout invalidation."""

    def test_ia009_logout_invalidates_session(self, client):
        """IA-009: After logout, token no longer works for /me."""
        token = register_and_get_token(client, "logout@example.com", "Pass1234!")

        # Verify token works
        resp = client.get("/api/v1/auth/me", headers=auth_header(token))
        assert resp.status_code == 200

        # Logout
        resp = client.post("/api/v1/auth/logout", headers=auth_header(token))
        assert resp.status_code == 200

        # Token should no longer work
        resp = client.get("/api/v1/auth/me", headers=auth_header(token))
        assert resp.status_code == 401


class TestAuthFullFlow:
    """IA-010: Complete auth lifecycle."""

    def test_ia010_full_auth_flow(self, client):
        """IA-010: Register → login → me → logout → me fails."""
        email, password = "flow@example.com", "FlowPass123!"

        # 1. Register
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password},
        )
        assert resp.status_code == 200
        reg_token = resp.json()["token"]

        # 2. Login (separate session)
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert resp.status_code == 200
        login_token = resp.json()["token"]
        assert login_token != reg_token  # Different session

        # 3. /me with login token
        resp = client.get("/api/v1/auth/me", headers=auth_header(login_token))
        assert resp.status_code == 200
        assert resp.json()["email"] == email

        # 4. Logout login session
        resp = client.post("/api/v1/auth/logout", headers=auth_header(login_token))
        assert resp.status_code == 200

        # 5. /me with logged-out token fails
        resp = client.get("/api/v1/auth/me", headers=auth_header(login_token))
        assert resp.status_code == 401

        # 6. Registration token still works (different session)
        resp = client.get("/api/v1/auth/me", headers=auth_header(reg_token))
        assert resp.status_code == 200
