"""
Test cases for Auth API.

Endpoints:
  - POST /api/v1/auth/register
  - POST /api/v1/auth/login
  - POST /api/v1/auth/logout
  - GET /api/v1/auth/me
"""

import time
import pytest
import httpx

API_V1 = "http://localhost:8000/api/v1"


class TestAuthRegister:
    """Tests for POST /auth/register."""

    @pytest.mark.asyncio
    async def test_register_success(self, client):
        """Should register new user successfully."""
        email = f"register_test_{int(time.time())}@example.com"

        resp = await client.post(
            f"{API_V1}/auth/register",
            json={"email": email, "password": "password123"}
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == email
        assert "expires_at" in data

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client):
        """Should reject duplicate email."""
        email = f"dup_test_{int(time.time())}@example.com"

        # First registration
        resp1 = await client.post(
            f"{API_V1}/auth/register",
            json={"email": email, "password": "password123"}
        )
        assert resp1.status_code == 200

        # Duplicate registration
        resp2 = await client.post(
            f"{API_V1}/auth/register",
            json={"email": email, "password": "different123"}
        )
        assert resp2.status_code == 400

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client):
        """Should reject invalid email format."""
        resp = await client.post(
            f"{API_V1}/auth/register",
            json={"email": "not-an-email", "password": "password123"}
        )
        assert resp.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_register_missing_password(self, client):
        """Should reject missing password."""
        resp = await client.post(
            f"{API_V1}/auth/register",
            json={"email": "test@example.com"}
        )
        assert resp.status_code == 422


class TestAuthLogin:
    """Tests for POST /auth/login."""

    @pytest.mark.asyncio
    async def test_login_success(self, client):
        """Should login with valid credentials."""
        email = f"login_test_{int(time.time())}@example.com"
        password = "password123"

        # Register first
        await client.post(
            f"{API_V1}/auth/register",
            json={"email": email, "password": password}
        )

        # Login
        resp = await client.post(
            f"{API_V1}/auth/login",
            json={"email": email, "password": password}
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["email"] == email

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client):
        """Should reject wrong password."""
        email = f"wrong_pw_{int(time.time())}@example.com"

        # Register
        await client.post(
            f"{API_V1}/auth/register",
            json={"email": email, "password": "correctpassword"}
        )

        # Login with wrong password
        resp = await client.post(
            f"{API_V1}/auth/login",
            json={"email": email, "password": "wrongpassword"}
        )

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client):
        """Should reject non-existent user."""
        resp = await client.post(
            f"{API_V1}/auth/login",
            json={"email": "nonexistent@example.com", "password": "password123"}
        )

        assert resp.status_code == 401


class TestAuthLogout:
    """Tests for POST /auth/logout."""

    @pytest.mark.asyncio
    async def test_logout_success(self, client, auth_headers):
        """Should logout successfully."""
        resp = await client.post(
            f"{API_V1}/auth/logout",
            headers=auth_headers
        )

        assert resp.status_code == 200
        assert "message" in resp.json()

    @pytest.mark.asyncio
    async def test_logout_invalidates_token(self, client, auth_headers):
        """Should invalidate token after logout."""
        # Logout
        await client.post(f"{API_V1}/auth/logout", headers=auth_headers)

        # Try to access protected endpoint
        resp = await client.get(f"{API_V1}/auth/me", headers=auth_headers)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_without_token(self, client):
        """Should handle logout without token gracefully."""
        resp = await client.post(f"{API_V1}/auth/logout")
        assert resp.status_code == 200


class TestAuthMe:
    """Tests for GET /auth/me."""

    @pytest.mark.asyncio
    async def test_get_me_success(self, client, auth_headers):
        """Should return current user info."""
        resp = await client.get(
            f"{API_V1}/auth/me",
            headers=auth_headers
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert "email" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_get_me_no_token(self, client):
        """Should reject request without token."""
        resp = await client.get(f"{API_V1}/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_invalid_token(self, client):
        """Should reject invalid token."""
        resp = await client.get(
            f"{API_V1}/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"}
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_malformed_header(self, client):
        """Should reject malformed auth header."""
        resp = await client.get(
            f"{API_V1}/auth/me",
            headers={"Authorization": "NotBearer token"}
        )
        assert resp.status_code == 401
