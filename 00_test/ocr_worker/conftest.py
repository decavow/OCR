"""
Pytest fixtures for OCR Worker tests.
"""

import sys
import asyncio
from pathlib import Path

import pytest
import pytest_asyncio
import httpx

# Add worker to path
WORKER_DIR = Path(__file__).parent.parent.parent / "worker"
sys.path.insert(0, str(WORKER_DIR))

BACKEND_URL = "http://localhost:8000"
API_V1 = f"{BACKEND_URL}/api/v1"
NATS_URL = "nats://localhost:4222"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def client():
    """Create async HTTP client."""
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=30.0) as client:
        yield client


@pytest_asyncio.fixture
async def auth_headers(client):
    """Get auth headers for authenticated requests."""
    import time
    email = f"worker_test_{int(time.time())}@example.com"
    resp = await client.post(
        f"{API_V1}/auth/register",
        json={"email": email, "password": "testpass123"}
    )
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_png():
    """Create minimal valid PNG file."""
    return bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
        0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,
        0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
        0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,
        0x44, 0xAE, 0x42, 0x60, 0x82,
    ])


@pytest.fixture
def test_image_with_text():
    """Create a test image with readable text."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io

        img = Image.new('RGB', (400, 100), color='white')
        draw = ImageDraw.Draw(img)

        text = "Hello OCR 123"
        try:
            font = ImageFont.truetype("arial.ttf", 32)
        except:
            font = ImageFont.load_default()

        draw.text((20, 30), text, fill='black', font=font)

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue(), text

    except ImportError:
        pytest.skip("PIL not installed")
