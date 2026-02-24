"""
Test Backend Flow: Register -> Login -> Upload -> Check NATS message.

Prerequisites:
  1. MinIO running: docker-compose -f docker-compose.infra.yml up -d minio
  2. NATS running: docker-compose -f docker-compose.infra.yml up -d nats
  3. Backend running: cd backend && uvicorn app.main:app --reload --port 8000

Usage: python test_backend_flow.py
"""

import asyncio
import json
import sys
import time
import httpx
import nats
from pathlib import Path


# Config
BACKEND_URL = "http://localhost:8000"
NATS_URL = "nats://localhost:4222"

# Test data
TEST_USER_EMAIL = f"test_{int(time.time())}@example.com"
TEST_USER_PASSWORD = "testpassword123"


async def test_backend_flow():
    """Test the complete backend flow."""
    print("\n" + "=" * 60)
    print("Backend Flow Test")
    print("=" * 60)
    results = []

    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=30.0) as client:
        # Test 1: Health check
        print("\nTest 1: Health check...")
        try:
            resp = await client.get("/health")
            if resp.status_code == 200:
                print(f"  [OK] Backend is healthy")
                results.append(("Health check", True))
            else:
                print(f"  [FAIL] Status: {resp.status_code}")
                results.append(("Health check", False))
        except Exception as e:
            print(f"  [FAIL] Cannot connect to backend: {e}")
            print("\n  >>> Please start the backend first:")
            print("  cd backend && uvicorn app.main:app --reload --port 8000")
            results.append(("Health check", False))
            return results

        # Test 2: Register
        print("\nTest 2: Register new user...")
        try:
            resp = await client.post(
                "/api/v1/auth/register",
                json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD},
            )
            if resp.status_code == 200:
                data = resp.json()
                token = data.get("token")
                user_id = data.get("user", {}).get("id")
                print(f"  [OK] Registered: {TEST_USER_EMAIL}")
                print(f"  User ID: {user_id}")
                print(f"  Token: {token[:20]}...")
                results.append(("Register", True))
            else:
                print(f"  [FAIL] Status: {resp.status_code}, Body: {resp.text}")
                results.append(("Register", False))
                token = None
        except Exception as e:
            print(f"  [FAIL] {e}")
            results.append(("Register", False))
            token = None

        if not token:
            print("\n  >>> Cannot continue without token")
            return results

        # Test 3: Get current user
        print("\nTest 3: Get current user (verify token)...")
        try:
            resp = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                print(f"  [OK] User email: {data.get('email')}")
                results.append(("Get me", True))
            else:
                print(f"  [FAIL] Status: {resp.status_code}, Body: {resp.text}")
                results.append(("Get me", False))
        except Exception as e:
            print(f"  [FAIL] {e}")
            results.append(("Get me", False))

        # Test 4: Upload file
        print("\nTest 4: Upload file...")
        try:
            # Create a test image (simple PNG)
            # Minimal 1x1 white PNG
            png_data = bytes([
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

            files = {
                "files": ("test_image.png", png_data, "image/png"),
            }
            params = {
                "output_format": "txt",
                "method": "ocr_text_raw",
                "tier": 0,
            }

            resp = await client.post(
                "/api/v1/upload",
                files=files,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                request_id = data.get("request_id")
                print(f"  [OK] Upload successful")
                print(f"  Request ID: {request_id}")
                print(f"  Status: {data.get('status')}")
                print(f"  Files: {len(data.get('files', []))}")
                results.append(("Upload", True))
            else:
                print(f"  [FAIL] Status: {resp.status_code}, Body: {resp.text}")
                results.append(("Upload", False))
                request_id = None
        except Exception as e:
            print(f"  [FAIL] {e}")
            import traceback
            traceback.print_exc()
            results.append(("Upload", False))
            request_id = None

    # Test 5: Check NATS message
    print("\nTest 5: Check NATS for job message...")
    try:
        nc = await nats.connect(NATS_URL)
        js = nc.jetstream()

        # Try to get stream info
        try:
            info = await js.stream_info("OCR_JOBS")
            print(f"  Stream: OCR_JOBS")
            print(f"  Messages: {info.state.messages}")
            print(f"  Bytes: {info.state.bytes}")

            if info.state.messages > 0:
                print(f"  [OK] Found {info.state.messages} message(s) in NATS stream")
                results.append(("NATS message", True))
            else:
                print(f"  [FAIL] No messages in stream")
                results.append(("NATS message", False))
        except Exception as e:
            print(f"  [FAIL] Cannot get stream info: {e}")
            results.append(("NATS message", False))

        await nc.close()

    except Exception as e:
        print(f"  [FAIL] Cannot connect to NATS: {e}")
        results.append(("NATS message", False))

    # Test 6: Logout
    print("\nTest 6: Logout...")
    try:
        async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=30.0) as client:
            resp = await client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                print(f"  [OK] Logged out")
                results.append(("Logout", True))
            else:
                print(f"  [FAIL] Status: {resp.status_code}, Body: {resp.text}")
                results.append(("Logout", False))
    except Exception as e:
        print(f"  [FAIL] {e}")
        results.append(("Logout", False))

    return results


def main():
    results = asyncio.run(test_backend_flow())

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "[OK]" if result else "[FAIL]"
        print(f"  {status} {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n>>> All backend flow tests passed!")
        print("Your upload -> NATS message flow is working!")
        return 0
    else:
        print("\n>>> Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
