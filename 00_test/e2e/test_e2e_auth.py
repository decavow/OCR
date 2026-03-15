"""E2E-002→003: Auth flow — register, login, me, logout."""

import time
import uuid
import pytest


# Use a shared email so register only happens once to avoid rate limits
_AUTH_TEST_EMAIL = f"e2e-authtest-{uuid.uuid4().hex[:8]}@test.com"
_AUTH_TEST_PASSWORD = "TestPass123!"


class TestAuthRegister:
    """Registration E2E tests (run first to avoid rate limits)."""

    def test_e2e002_register_new_user(self, anon_client):
        """New user registration should return token."""
        resp = anon_client.post("/auth/register", json={
            "email": _AUTH_TEST_EMAIL,
            "password": _AUTH_TEST_PASSWORD,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["email"] == _AUTH_TEST_EMAIL
        assert data["user"]["is_admin"] is False
        assert "expires_at" in data

    def test_e2e002b_register_duplicate_email(self, anon_client):
        """Registering with existing email should fail."""
        # _AUTH_TEST_EMAIL was already registered above
        resp = anon_client.post("/auth/register", json={
            "email": _AUTH_TEST_EMAIL,
            "password": _AUTH_TEST_PASSWORD,
        })
        assert resp.status_code in (400, 429)  # 400 duplicate or 429 rate limited


class TestAuthLogin:
    """Login E2E tests (uses the user registered in TestAuthRegister)."""

    def test_e2e003_login_existing_user(self, anon_client):
        """Login with valid credentials should return token."""
        resp = anon_client.post("/auth/login", json={
            "email": _AUTH_TEST_EMAIL,
            "password": _AUTH_TEST_PASSWORD,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["email"] == _AUTH_TEST_EMAIL

    def test_e2e003b_login_wrong_password(self, anon_client):
        """Login with wrong password should fail."""
        resp = anon_client.post("/auth/login", json={
            "email": _AUTH_TEST_EMAIL,
            "password": "WrongPassword!",
        })
        assert resp.status_code == 401

    def test_e2e003c_login_nonexistent_user(self, anon_client):
        """Login with non-existent email should fail."""
        resp = anon_client.post("/auth/login", json={
            "email": "nonexistent@test.com",
            "password": "TestPass123!",
        })
        assert resp.status_code == 401


class TestAuthProtected:
    """Protected endpoint access tests."""

    def test_e2e003d_get_current_user(self, client):
        """GET /auth/me should return current user info."""
        resp = client.get("/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert "email" in data
        assert "id" in data

    def test_e2e014_auth_required_for_requests(self, anon_client):
        """Accessing protected endpoints without token should return 401."""
        resp = anon_client.get("/requests")
        assert resp.status_code == 401

    def test_e2e014b_invalid_token(self, base_url):
        """Using invalid token should return 401."""
        import httpx
        with httpx.Client(
            base_url=base_url,
            headers={"Authorization": "Bearer invalid-token-12345"},
            timeout=10,
        ) as c:
            resp = c.get("/requests")
            assert resp.status_code == 401
