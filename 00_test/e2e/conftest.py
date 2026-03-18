"""
E2E test fixtures — real services, real HTTP.

Requires running: Backend (8080), MinIO (9000), NATS (4222).
Worker is simulated via internal API calls.
"""

import os
import time
import uuid
import pytest
import httpx

# ─── Configuration ──────────────────────────────────────────────────────────
BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8080/api/v1")
BACKEND_URL = BASE_URL.rsplit("/api/v1", 1)[0]

E2E_USER_EMAIL = f"e2e-user-{uuid.uuid4().hex[:8]}@test.com"
E2E_USER_PASSWORD = "E2eTestPass123!"

E2E_ADMIN_EMAIL = "e2e-admin@test.com"
E2E_ADMIN_PASSWORD = "E2eAdmin123!"

WORKER_SERVICE_TYPE = f"e2e-ocr-worker-{uuid.uuid4().hex[:8]}"
WORKER_INSTANCE_ID = f"e2e-instance-{uuid.uuid4().hex[:12]}"


# ─── Session-scoped: verify backend is running ──────────────────────────────
@pytest.fixture(scope="session")
def base_url():
    """Verify backend is running and return base URL."""
    try:
        resp = httpx.get(f"{BACKEND_URL}/api/v1/health", timeout=5)
        assert resp.status_code == 200, f"Backend unhealthy: {resp.text}"
    except httpx.ConnectError:
        pytest.skip(f"Backend not running at {BACKEND_URL}")
    return BASE_URL


# ─── Admin token (session-scoped) ───────────────────────────────────────────
@pytest.fixture(scope="session")
def admin_token(base_url):
    """Login as admin user, return token."""
    with httpx.Client(base_url=base_url, timeout=10) as client:
        resp = client.post("/auth/login", json={
            "email": E2E_ADMIN_EMAIL,
            "password": E2E_ADMIN_PASSWORD,
        })
        if resp.status_code != 200:
            pytest.skip(f"Admin login failed: {resp.text}")
        return resp.json()["token"]


# ─── Regular user token (session-scoped) ────────────────────────────────────
@pytest.fixture(scope="session")
def user_token(base_url):
    """Register a unique test user, return token. Handles rate limiting."""
    with httpx.Client(base_url=base_url, timeout=10) as client:
        # Try register with retry for rate limiting
        for attempt in range(3):
            resp = client.post("/auth/register", json={
                "email": E2E_USER_EMAIL,
                "password": E2E_USER_PASSWORD,
            })
            if resp.status_code == 200:
                return resp.json()["token"]
            if resp.status_code == 429:
                time.sleep(2)
                continue
            if resp.status_code == 400:
                # User exists → try login
                break

        # Fallback: login
        resp = client.post("/auth/login", json={
            "email": E2E_USER_EMAIL,
            "password": E2E_USER_PASSWORD,
        })
        assert resp.status_code == 200, f"Auth failed for {E2E_USER_EMAIL}: {resp.text}"
        return resp.json()["token"]


# ─── Authenticated clients ──────────────────────────────────────────────────
@pytest.fixture
def client(base_url, user_token):
    """Authenticated httpx client (regular user)."""
    with httpx.Client(
        base_url=base_url,
        headers={"Authorization": f"Bearer {user_token}"},
        timeout=30.0,
    ) as c:
        yield c


@pytest.fixture
def admin_client(base_url, admin_token):
    """Authenticated httpx client (admin user)."""
    with httpx.Client(
        base_url=base_url,
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30.0,
    ) as c:
        yield c


@pytest.fixture
def anon_client(base_url):
    """Unauthenticated httpx client."""
    with httpx.Client(base_url=base_url, timeout=10.0) as c:
        yield c


# ─── Worker setup: register + approve + get access_key ──────────────────────
@pytest.fixture(scope="session")
def worker_setup(base_url, admin_token):
    """
    Register a fake worker, approve its service type, return setup info.

    Returns dict with: service_type, instance_id, access_key
    """
    with httpx.Client(base_url=base_url, timeout=10) as client:
        # Step 1: Register worker (creates PENDING service type)
        reg_resp = client.post("/internal/register", json={
            "service_type": WORKER_SERVICE_TYPE,
            "instance_id": WORKER_INSTANCE_ID,
            "display_name": "E2E Test Worker",
            "description": "Simulated worker for E2E testing",
            "allowed_methods": ["ocr_paddle_text"],
            "allowed_tiers": [0],
            "supported_output_formats": ["txt", "json"],
            "engine_info": {"name": "E2E-TestEngine", "version": "1.0.0"},
            "dev_contact": "e2e@test.com",
        })
        assert reg_resp.status_code == 200, f"Worker register failed: {reg_resp.text}"
        reg_data = reg_resp.json()
        assert reg_data["type_status"] in ("PENDING", "APPROVED")

        # Step 2: Admin approves the service type
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        approve_resp = client.post(
            f"/admin/service-types/{WORKER_SERVICE_TYPE}/approve",
            headers=admin_headers,
        )
        if approve_resp.status_code == 400 and "already approved" in approve_resp.text:
            # Already approved — get the access key
            type_resp = client.get(
                f"/admin/service-types/{WORKER_SERVICE_TYPE}",
                headers=admin_headers,
            )
            access_key = type_resp.json()["access_key"]
        else:
            assert approve_resp.status_code == 200, f"Approve failed: {approve_resp.text}"
            access_key = approve_resp.json()["access_key"]

        assert access_key, "No access_key returned after approval"

        # Step 3: Worker heartbeat to get activated (need access_key since auto-activated)
        hb_resp = client.post(
            "/internal/heartbeat",
            json={
                "instance_id": WORKER_INSTANCE_ID,
                "status": "idle",
            },
            headers={"X-Access-Key": access_key},
        )
        assert hb_resp.status_code == 200, f"Heartbeat failed: {hb_resp.text}"

        return {
            "service_type": WORKER_SERVICE_TYPE,
            "instance_id": WORKER_INSTANCE_ID,
            "access_key": access_key,
        }


# ─── Keep worker alive: send heartbeat before each test that needs it ──────
@pytest.fixture(autouse=False)
def refresh_worker(base_url, worker_setup):
    """Send a heartbeat to keep the simulated worker ACTIVE."""
    with httpx.Client(base_url=base_url, timeout=10) as client:
        client.post(
            "/internal/heartbeat",
            json={
                "instance_id": worker_setup["instance_id"],
                "status": "idle",
            },
            headers={"X-Access-Key": worker_setup["access_key"]},
        )


# ─── Sample files ───────────────────────────────────────────────────────────
@pytest.fixture
def sample_png():
    """Minimal valid 1x1 white PNG (67 bytes)."""
    return (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05"
        b"\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )


@pytest.fixture
def sample_pdf():
    """Minimal valid 1-page PDF."""
    return (
        b"%PDF-1.0\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\n"
        b"startxref\n190\n%%EOF"
    )
