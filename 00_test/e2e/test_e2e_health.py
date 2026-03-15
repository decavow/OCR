"""E2E-001: Health check — verify all services are running."""

import pytest


class TestHealthCheck:
    """Smoke test: backend + infrastructure health."""

    def test_e2e001_health_endpoint_returns_healthy(self, anon_client):
        """Health endpoint should report healthy when all services are up."""
        resp = anon_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "degraded")
        assert data["database"] == "ok"
        assert data["nats"] == "ok"
        assert data["minio"] == "ok"

    def test_e2e001b_health_no_auth_required(self, anon_client):
        """Health endpoint should be accessible without authentication."""
        resp = anon_client.get("/health")
        assert resp.status_code == 200
