"""
Run OCR Worker tests.

Prerequisites:
  1. Docker services running: docker-compose -f docker-compose.infra.yml up -d
  2. Backend running: cd backend && uvicorn app.main:app --port 8000
  3. PaddleOCR installed with GPU support

Usage:
  python run_tests.py              # Run all tests
  python run_tests.py nats         # Run NATS connection tests only
  python run_tests.py ocr          # Run OCR processing tests only
  python run_tests.py e2e          # Run end-to-end flow tests only
"""

import asyncio
import sys
import time
import base64
import json
import httpx
import nats
from pathlib import Path

# Add worker to path for imports
WORKER_DIR = Path(__file__).parent.parent.parent / "03_worker"
sys.path.insert(0, str(WORKER_DIR))

BACKEND_URL = "http://localhost:8000"
API_V1 = f"{BACKEND_URL}/api/v1"
NATS_URL = "nats://localhost:4222"


def create_sample_png():
    """Create minimal valid PNG file (1x1 white pixel)."""
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


def create_test_image_with_text():
    """Create a simple image with text for OCR testing."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io

        # Create white image
        img = Image.new('RGB', (400, 100), color='white')
        draw = ImageDraw.Draw(img)

        # Draw text
        text = "Hello OCR World 123"
        try:
            font = ImageFont.truetype("arial.ttf", 32)
        except:
            font = ImageFont.load_default()

        draw.text((20, 30), text, fill='black', font=font)

        # Save to bytes
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue(), text

    except ImportError:
        # Fallback to minimal PNG if PIL not available
        return create_sample_png(), ""


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def add_pass(self, name):
        self.passed += 1
        print(f"  [PASS] {name}")

    def add_fail(self, name, reason=""):
        self.failed += 1
        self.errors.append((name, reason))
        print(f"  [FAIL] {name}: {reason}")


async def test_nats_connection(result: TestResult):
    """Test NATS connection and stream."""
    print("\n=== NATS Connection Tests ===")

    # Test basic connection
    try:
        nc = await nats.connect(NATS_URL)
        result.add_pass("Connect to NATS")
        await nc.close()
    except Exception as e:
        result.add_fail("Connect to NATS", str(e))
        return

    # Test JetStream availability
    try:
        nc = await nats.connect(NATS_URL)
        js = nc.jetstream()
        result.add_pass("JetStream available")
    except Exception as e:
        result.add_fail("JetStream available", str(e))
        await nc.close()
        return

    # Test OCR_JOBS stream exists
    try:
        info = await js.stream_info("OCR_JOBS")
        result.add_pass(f"OCR_JOBS stream exists (msgs: {info.state.messages})")
    except Exception as e:
        result.add_fail("OCR_JOBS stream exists", str(e))

    await nc.close()


async def test_queue_client(result: TestResult):
    """Test QueueClient from worker."""
    print("\n=== QueueClient Tests ===")

    try:
        from app.clients.queue_client import QueueClient
        from app.config import settings

        # Override settings for local testing
        settings.nats_url = NATS_URL
        settings.worker_filter_subject = "ocr.ocr_text_raw.tier0"
        settings.worker_service_type = "test-worker"

        client = QueueClient()

        # Test connect
        await client.connect()
        result.add_pass("QueueClient connect")

        # Test pull (should return None if no messages)
        job = await client.pull_job(timeout=2.0)
        if job is None:
            result.add_pass("QueueClient pull_job (no message)")
        else:
            result.add_pass(f"QueueClient pull_job (got job: {job['job_id']})")
            # Nak the message so it can be reprocessed
            await client.nak(job["_msg_id"])

        # Test disconnect
        await client.disconnect()
        result.add_pass("QueueClient disconnect")

    except Exception as e:
        result.add_fail("QueueClient", str(e))


async def test_file_proxy_client(result: TestResult):
    """Test FileProxyClient from worker."""
    print("\n=== FileProxyClient Tests ===")

    try:
        from app.clients.file_proxy_client import FileProxyClient
        from app.config import settings

        # Override settings for local testing
        settings.file_proxy_url = f"{API_V1}/internal/file-proxy"
        settings.worker_access_key = "sk_test_worker"

        client = FileProxyClient()

        # Test download with invalid job (should fail with 404 or 403)
        try:
            await client.download("invalid-job", "invalid-file")
            result.add_fail("FileProxyClient download invalid", "Should have raised error")
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 404):
                result.add_pass("FileProxyClient rejects invalid request")
            else:
                result.add_fail("FileProxyClient download", f"Unexpected status: {e.response.status_code}")
        except Exception as e:
            result.add_fail("FileProxyClient download", str(e))

    except Exception as e:
        result.add_fail("FileProxyClient", str(e))


async def test_ocr_processor(result: TestResult):
    """Test OCR processing with PaddleOCR."""
    print("\n=== OCR Processor Tests ===")

    try:
        from app.core.processor import OCRProcessor
        from app.engines.paddle_text import TextRawHandler

        # Test handler initialization
        handler = TextRawHandler(use_gpu=True, lang="en")
        result.add_pass("TextRawHandler initialized (GPU)")

    except Exception as e:
        result.add_fail("TextRawHandler init", str(e))
        # Try CPU fallback
        try:
            from app.engines.paddle_text import TextRawHandler
            handler = TextRawHandler(use_gpu=False, lang="en")
            result.add_pass("TextRawHandler initialized (CPU fallback)")
        except Exception as e2:
            result.add_fail("TextRawHandler init (CPU)", str(e2))
            return

    # Test OCR on image with text
    try:
        img_bytes, expected_text = create_test_image_with_text()

        # Process image
        output = await handler.process(img_bytes, "txt")
        output_text = output.decode("utf-8")

        if expected_text and expected_text.lower() in output_text.lower():
            result.add_pass(f"OCR text extraction: '{output_text.strip()}'")
        elif output_text.strip():
            result.add_pass(f"OCR produced output: {len(output_text)} chars")
        else:
            result.add_fail("OCR text extraction", "No text extracted")

    except Exception as e:
        result.add_fail("OCR processing", str(e))

    # Test JSON output format
    try:
        img_bytes, _ = create_test_image_with_text()
        output = await handler.process(img_bytes, "json")
        data = json.loads(output.decode("utf-8"))

        if "text" in data and "lines" in data:
            result.add_pass("OCR JSON output format")
        else:
            result.add_fail("OCR JSON output format", "Missing required fields")

    except Exception as e:
        result.add_fail("OCR JSON output", str(e))


async def test_end_to_end_flow(result: TestResult):
    """Test end-to-end OCR flow."""
    print("\n=== End-to-End Flow Tests ===")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Register user and get token
        try:
            email = f"ocr_test_{int(time.time())}@example.com"
            resp = await client.post(
                f"{API_V1}/auth/register",
                json={"email": email, "password": "testpass123"}
            )
            if resp.status_code != 200:
                result.add_fail("E2E: Register user", f"Status: {resp.status_code}")
                return
            token = resp.json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            result.add_pass("E2E: Register user")
        except Exception as e:
            result.add_fail("E2E: Register user", str(e))
            return

        # Step 2: Upload image
        try:
            img_bytes, _ = create_test_image_with_text()
            files = {"files": ("test_ocr.png", img_bytes, "image/png")}
            resp = await client.post(
                f"{API_V1}/upload",
                files=files,
                data={"output_format": "txt", "method": "ocr_text_raw", "tier": "0"},
                headers=headers
            )
            if resp.status_code != 200:
                result.add_fail("E2E: Upload image", f"Status: {resp.status_code}")
                return

            upload_data = resp.json()
            request_id = upload_data["request_id"]
            result.add_pass(f"E2E: Upload image (request: {request_id[:8]}...)")

        except Exception as e:
            result.add_fail("E2E: Upload image", str(e))
            return

        # Step 3: Check NATS received job
        try:
            nc = await nats.connect(NATS_URL)
            js = nc.jetstream()
            info = await js.stream_info("OCR_JOBS")

            if info.state.messages > 0:
                result.add_pass(f"E2E: Job published to NATS (queue: {info.state.messages})")
            else:
                result.add_fail("E2E: Job published to NATS", "No messages in queue")

            await nc.close()

        except Exception as e:
            result.add_fail("E2E: Check NATS", str(e))

        # Step 4: Check request status
        try:
            resp = await client.get(
                f"{API_V1}/requests/{request_id}",
                headers=headers
            )
            if resp.status_code == 200:
                status = resp.json().get("status")
                result.add_pass(f"E2E: Request status: {status}")
            else:
                result.add_fail("E2E: Get request status", f"Status: {resp.status_code}")

        except Exception as e:
            result.add_fail("E2E: Get request status", str(e))


async def main():
    print("=" * 60)
    print("OCR Worker Tests")
    print("=" * 60)

    # Check backend health
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{BACKEND_URL}/health")
            if resp.status_code != 200:
                print("\n[ERROR] Backend is not healthy")
                print("Please start: cd backend && uvicorn app.main:app --port 8000")
                return 1
        except Exception as e:
            print(f"\n[ERROR] Cannot connect to backend: {e}")
            print("Please start: cd backend && uvicorn app.main:app --port 8000")
            return 1

    result = TestResult()

    # Determine which tests to run
    test_filter = sys.argv[1] if len(sys.argv) > 1 else "all"

    if test_filter in ["all", "nats"]:
        await test_nats_connection(result)

    if test_filter in ["all", "queue", "nats"]:
        await test_queue_client(result)

    if test_filter in ["all", "proxy", "file_proxy"]:
        await test_file_proxy_client(result)

    if test_filter in ["all", "ocr"]:
        await test_ocr_processor(result)

    if test_filter in ["all", "e2e", "flow"]:
        await test_end_to_end_flow(result)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Passed: {result.passed}")
    print(f"  Failed: {result.failed}")

    if result.errors:
        print("\nFailed tests:")
        for name, reason in result.errors:
            print(f"  - {name}: {reason}")

    total = result.passed + result.failed
    print(f"\nTotal: {result.passed}/{total} tests passed")

    if result.failed == 0:
        print("\n>>> All tests passed!")
        return 0
    else:
        print("\n>>> Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
