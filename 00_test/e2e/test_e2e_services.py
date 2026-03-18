"""E2E: Service discovery — list available services for upload."""

import pytest


@pytest.mark.usefixtures("refresh_worker")
class TestServiceDiscovery:
    """Service availability E2E tests."""

    def test_list_available_services(self, client, worker_setup):
        """After worker registration + approval, service should be listed."""
        resp = client.get("/services/available")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

        # Find our E2E service
        service_ids = [s["id"] for s in data["items"]]
        assert worker_setup["service_type"] in service_ids

        # Check service details
        our_service = next(
            s for s in data["items"]
            if s["id"] == worker_setup["service_type"]
        )
        assert "ocr_paddle_text" in our_service["allowed_methods"]
        assert 0 in our_service["allowed_tiers"]
        assert our_service["active_instances"] >= 1

    def test_list_requests_empty_initially(self, client):
        """New user should have some requests (from other tests) or empty."""
        resp = client.get("/requests")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
