"""E2E-007→009: Worker internal API — register, heartbeat, job status."""

import uuid
import pytest


class TestWorkerRegistration:
    """Worker registration E2E tests."""

    def test_e2e007_worker_register_new_type(self, anon_client):
        """New worker registration should create PENDING service type."""
        service_type = f"e2e-test-{uuid.uuid4().hex[:8]}"
        instance_id = f"e2e-inst-{uuid.uuid4().hex[:8]}"


        resp = anon_client.post("/internal/register", json={
            "service_type": service_type,
            "instance_id": instance_id,
            "display_name": "Test Worker",
            "description": "E2E test worker",
            "allowed_methods": ["ocr_paddle_text"],
            "allowed_tiers": [0],
            "supported_output_formats": ["txt"],
            "engine_info": {"name": "TestEngine", "version": "1.0"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["instance_id"] == instance_id
        assert data["type_status"] == "PENDING"
        assert data["instance_status"] == "WAITING"

    def test_e2e007b_worker_register_approved_type(self, anon_client, worker_setup):
        """Registering with an approved service type should return access_key."""
        new_instance = f"e2e-inst-{uuid.uuid4().hex[:8]}"

        resp = anon_client.post("/internal/register", json={
            "service_type": worker_setup["service_type"],
            "instance_id": new_instance,
            "display_name": "Second Worker Instance",
            "allowed_methods": ["ocr_paddle_text"],
            "allowed_tiers": [0],
            "supported_output_formats": ["txt"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["type_status"] == "APPROVED"
        assert data.get("access_key") == worker_setup["access_key"]


class TestWorkerHeartbeat:
    """Worker heartbeat E2E tests."""

    def test_e2e008_heartbeat_active_worker(self, base_url, worker_setup):
        """Active worker heartbeat should succeed with action=continue."""
        import httpx
        with httpx.Client(base_url=base_url, timeout=10) as c:
            resp = c.post(
                "/internal/heartbeat",
                json={
                    "instance_id": worker_setup["instance_id"],
                    "status": "idle",
                },
                headers={"X-Access-Key": worker_setup["access_key"]},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["action"] == "continue"

    def test_e2e008b_heartbeat_unknown_instance(self, anon_client):
        """Heartbeat from unknown instance should return 404."""
        resp = anon_client.post("/internal/heartbeat", json={
            "instance_id": "nonexistent-instance-id",
            "status": "idle",
        })
        assert resp.status_code == 404


class TestWorkerDeregister:
    """Worker deregistration E2E tests."""

    def test_e2e007c_worker_deregister(self, anon_client):
        """Deregistering a worker should mark it as DEAD."""
        # Register first
        service_type = f"e2e-dereg-{uuid.uuid4().hex[:8]}"
        instance_id = f"e2e-inst-{uuid.uuid4().hex[:8]}"


        anon_client.post("/internal/register", json={
            "service_type": service_type,
            "instance_id": instance_id,
            "display_name": "DeregTest",
            "allowed_methods": ["ocr_paddle_text"],
            "allowed_tiers": [0],
            "supported_output_formats": ["txt"],
        })

        # Deregister
        resp = anon_client.post("/internal/deregister", json={
            "instance_id": instance_id,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["instance_id"] == instance_id
