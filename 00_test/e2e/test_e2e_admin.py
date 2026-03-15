"""E2E: Admin API — service type management."""

import uuid
import pytest


class TestAdminServiceTypes:
    """Admin service type management E2E tests."""

    def test_admin_list_service_types(self, admin_client, worker_setup):
        """Admin should be able to list all service types."""
        resp = admin_client.get("/admin/service-types")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        type_ids = [t["id"] for t in data["items"]]
        assert worker_setup["service_type"] in type_ids

    def test_admin_get_service_type_detail(self, admin_client, worker_setup):
        """Admin should be able to get service type details."""
        resp = admin_client.get(f"/admin/service-types/{worker_setup['service_type']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == worker_setup["service_type"]
        assert data["status"] == "APPROVED"
        assert data["access_key"] is not None

    def test_admin_approve_reject_flow(self, admin_client, anon_client):
        """Full admin flow: register → approve → disable → enable."""
        service_type = f"e2e-admin-flow-{uuid.uuid4().hex[:8]}"
        instance_id = f"e2e-inst-{uuid.uuid4().hex[:8]}"

        # Register
        anon_client.post("/internal/register", json={
            "service_type": service_type,
            "instance_id": instance_id,
            "display_name": "Admin Flow Test",
            "allowed_methods": ["ocr_paddle_text"],
            "allowed_tiers": [0],
            "supported_output_formats": ["txt"],
        })

        # Approve
        resp = admin_client.post(f"/admin/service-types/{service_type}/approve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "APPROVED"
        assert resp.json()["access_key"] is not None

        # Disable
        resp = admin_client.post(f"/admin/service-types/{service_type}/disable")
        assert resp.status_code == 200
        assert resp.json()["status"] == "DISABLED"

        # Enable
        resp = admin_client.post(f"/admin/service-types/{service_type}/enable")
        assert resp.status_code == 200
        assert resp.json()["status"] == "APPROVED"

    def test_admin_required_for_service_management(self, client, worker_setup):
        """Regular user cannot access admin endpoints."""
        resp = client.get("/admin/service-types")
        assert resp.status_code == 403

    def test_admin_dashboard_stats(self, admin_client):
        """Admin dashboard stats should return system overview."""
        resp = admin_client.get("/admin/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_users" in data
        assert "total_requests" in data
        assert "total_jobs" in data
