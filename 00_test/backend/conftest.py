"""
Pytest configuration and fixtures for backend tests.
"""

import os
import sys
import asyncio
from pathlib import Path

import pytest
import httpx

# Add backend to path
backend_path = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

# Override settings for testing
os.environ["DATABASE_URL"] = "sqlite:///./test_data/test.db"
os.environ["MINIO_ENDPOINT"] = "localhost:9000"
os.environ["MINIO_ACCESS_KEY"] = "minioadmin"
os.environ["MINIO_SECRET_KEY"] = "minioadmin"
os.environ["NATS_URL"] = "nats://localhost:4222"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["SEED_SERVICES"] = "test-worker:sk_test_key:text_raw:0"

# Test constants
BASE_URL = "http://localhost:8000"
API_V1 = f"{BASE_URL}/api/v1"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def client():
    """HTTP client for API tests."""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        yield client


@pytest.fixture
async def auth_headers(client):
    """Get auth headers with valid token."""
    import time
    email = f"test_{int(time.time())}@example.com"

    resp = await client.post(
        f"{API_V1}/auth/register",
        json={"email": email, "password": "testpass123"}
    )
    assert resp.status_code == 200
    token = resp.json()["token"]

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_png():
    """Minimal valid PNG file."""
    return bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
        0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,
        0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
        0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,  # IEND chunk
        0x44, 0xAE, 0x42, 0x60, 0x82,
    ])


@pytest.fixture
def sample_pdf():
    """Minimal valid PDF file."""
    return b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n0000000101 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF"
