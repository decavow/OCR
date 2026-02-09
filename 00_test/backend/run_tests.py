"""
Run backend API tests.

Prerequisites:
  1. Docker services running: docker-compose -f docker-compose.infra.yml up -d
  2. Backend running: cd backend && uvicorn app.main:app --port 8000

Usage:
  python run_tests.py           # Run all tests
  python run_tests.py auth      # Run auth tests only
  python run_tests.py upload    # Run upload tests only
"""

import asyncio
import sys
import time
import httpx
import base64

BASE_URL = "http://localhost:8000"
API_V1 = f"{BASE_URL}/api/v1"


def create_sample_png():
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


async def test_auth(client: httpx.AsyncClient, result: TestResult):
    """Test auth endpoints."""
    print("\n=== Auth Tests ===")

    email = f"test_{int(time.time())}@example.com"
    password = "testpass123"
    token = None

    # Test register
    try:
        resp = await client.post(
            f"{API_V1}/auth/register",
            json={"email": email, "password": password}
        )
        if resp.status_code == 200 and "token" in resp.json():
            token = resp.json()["token"]
            result.add_pass("Register new user")
        else:
            result.add_fail("Register new user", f"Status: {resp.status_code}")
    except Exception as e:
        result.add_fail("Register new user", str(e))

    # Test register duplicate
    try:
        resp = await client.post(
            f"{API_V1}/auth/register",
            json={"email": email, "password": password}
        )
        if resp.status_code == 400:
            result.add_pass("Reject duplicate email")
        else:
            result.add_fail("Reject duplicate email", f"Status: {resp.status_code}")
    except Exception as e:
        result.add_fail("Reject duplicate email", str(e))

    # Test login
    try:
        resp = await client.post(
            f"{API_V1}/auth/login",
            json={"email": email, "password": password}
        )
        if resp.status_code == 200:
            result.add_pass("Login with valid credentials")
        else:
            result.add_fail("Login with valid credentials", f"Status: {resp.status_code}")
    except Exception as e:
        result.add_fail("Login with valid credentials", str(e))

    # Test login wrong password
    try:
        resp = await client.post(
            f"{API_V1}/auth/login",
            json={"email": email, "password": "wrongpass"}
        )
        if resp.status_code == 401:
            result.add_pass("Reject wrong password")
        else:
            result.add_fail("Reject wrong password", f"Status: {resp.status_code}")
    except Exception as e:
        result.add_fail("Reject wrong password", str(e))

    # Test get me
    if token:
        try:
            resp = await client.get(
                f"{API_V1}/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            if resp.status_code == 200 and resp.json().get("email") == email:
                result.add_pass("Get current user")
            else:
                result.add_fail("Get current user", f"Status: {resp.status_code}")
        except Exception as e:
            result.add_fail("Get current user", str(e))

    # Test get me without token
    try:
        resp = await client.get(f"{API_V1}/auth/me")
        if resp.status_code == 401:
            result.add_pass("Reject request without token")
        else:
            result.add_fail("Reject request without token", f"Status: {resp.status_code}")
    except Exception as e:
        result.add_fail("Reject request without token", str(e))

    # Test logout
    if token:
        try:
            resp = await client.post(
                f"{API_V1}/auth/logout",
                headers={"Authorization": f"Bearer {token}"}
            )
            if resp.status_code == 200:
                result.add_pass("Logout")
            else:
                result.add_fail("Logout", f"Status: {resp.status_code}")
        except Exception as e:
            result.add_fail("Logout", str(e))

        # Test token invalidated after logout
        try:
            resp = await client.get(
                f"{API_V1}/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            if resp.status_code == 401:
                result.add_pass("Token invalidated after logout")
            else:
                result.add_fail("Token invalidated after logout", f"Status: {resp.status_code}")
        except Exception as e:
            result.add_fail("Token invalidated after logout", str(e))

    return token


async def test_upload(client: httpx.AsyncClient, result: TestResult):
    """Test upload endpoints."""
    print("\n=== Upload Tests ===")

    # Get fresh token
    email = f"upload_test_{int(time.time())}@example.com"
    resp = await client.post(
        f"{API_V1}/auth/register",
        json={"email": email, "password": "testpass123"}
    )
    token = resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    sample_png = create_sample_png()

    # Test single file upload
    try:
        files = {"files": ("test.png", sample_png, "image/png")}
        resp = await client.post(f"{API_V1}/upload", files=files, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("total_files") == 1 and len(data.get("files", [])) == 1:
                result.add_pass("Upload single file")
            else:
                result.add_fail("Upload single file", "Wrong response structure")
        else:
            result.add_fail("Upload single file", f"Status: {resp.status_code}, Body: {resp.text}")
    except Exception as e:
        result.add_fail("Upload single file", str(e))

    # Test multiple files upload
    try:
        files = [
            ("files", ("test1.png", sample_png, "image/png")),
            ("files", ("test2.png", sample_png, "image/png")),
        ]
        resp = await client.post(f"{API_V1}/upload", files=files, headers=headers)
        if resp.status_code == 200 and resp.json().get("total_files") == 2:
            result.add_pass("Upload multiple files")
        else:
            result.add_fail("Upload multiple files", f"Status: {resp.status_code}")
    except Exception as e:
        result.add_fail("Upload multiple files", str(e))

    # Test upload with parameters
    try:
        files = {"files": ("test.png", sample_png, "image/png")}
        resp = await client.post(
            f"{API_V1}/upload",
            files=files,
            params={"output_format": "json", "method": "text_raw", "tier": 0},
            headers=headers
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("output_format") == "json" and data.get("method") == "text_raw":
                result.add_pass("Upload with parameters")
            else:
                result.add_fail("Upload with parameters", "Wrong parameters in response")
        else:
            result.add_fail("Upload with parameters", f"Status: {resp.status_code}")
    except Exception as e:
        result.add_fail("Upload with parameters", str(e))

    # Test upload without auth
    try:
        files = {"files": ("test.png", sample_png, "image/png")}
        resp = await client.post(f"{API_V1}/upload", files=files)
        if resp.status_code == 401:
            result.add_pass("Reject upload without auth")
        else:
            result.add_fail("Reject upload without auth", f"Status: {resp.status_code}")
    except Exception as e:
        result.add_fail("Reject upload without auth", str(e))

    # Test upload invalid file type
    try:
        files = {"files": ("test.exe", b"MZ\x00\x00", "application/x-msdownload")}
        resp = await client.post(f"{API_V1}/upload", files=files, headers=headers)
        if resp.status_code == 400:
            result.add_pass("Reject invalid file type")
        else:
            result.add_fail("Reject invalid file type", f"Status: {resp.status_code}")
    except Exception as e:
        result.add_fail("Reject invalid file type", str(e))


async def test_file_proxy(client: httpx.AsyncClient, result: TestResult):
    """Test file proxy endpoints."""
    print("\n=== File Proxy Tests ===")

    # Test download without access key
    try:
        resp = await client.post(
            f"{API_V1}/internal/file-proxy/download",
            json={"job_id": "test", "file_id": "test"}
        )
        if resp.status_code == 422:
            result.add_pass("Download requires access key")
        else:
            result.add_fail("Download requires access key", f"Status: {resp.status_code}")
    except Exception as e:
        result.add_fail("Download requires access key", str(e))

    # Test download with invalid access key
    try:
        resp = await client.post(
            f"{API_V1}/internal/file-proxy/download",
            json={"job_id": "test", "file_id": "test"},
            headers={"X-Access-Key": "invalid_key"}
        )
        if resp.status_code == 403:
            result.add_pass("Reject invalid access key")
        else:
            result.add_fail("Reject invalid access key", f"Status: {resp.status_code}")
    except Exception as e:
        result.add_fail("Reject invalid access key", str(e))

    # Test upload without access key
    try:
        content = base64.b64encode(b"test content").decode()
        resp = await client.post(
            f"{API_V1}/internal/file-proxy/upload",
            json={"job_id": "test", "file_id": "test", "content": content, "content_type": "text/plain"}
        )
        if resp.status_code == 422:
            result.add_pass("Upload requires access key")
        else:
            result.add_fail("Upload requires access key", f"Status: {resp.status_code}")
    except Exception as e:
        result.add_fail("Upload requires access key", str(e))


async def test_health(client: httpx.AsyncClient, result: TestResult):
    """Test health endpoints."""
    print("\n=== Health Tests ===")

    try:
        resp = await client.get("/health")
        if resp.status_code == 200 and resp.json().get("status") == "healthy":
            result.add_pass("Root health check")
        else:
            result.add_fail("Root health check", f"Status: {resp.status_code}")
    except Exception as e:
        result.add_fail("Root health check", str(e))

    try:
        resp = await client.get(f"{API_V1}/health")
        if resp.status_code == 200:
            result.add_pass("API health check")
        else:
            result.add_fail("API health check", f"Status: {resp.status_code}")
    except Exception as e:
        result.add_fail("API health check", str(e))


async def main():
    print("=" * 60)
    print("Backend API Tests")
    print("=" * 60)

    # Check if backend is running
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        try:
            resp = await client.get("/health")
            if resp.status_code != 200:
                print("\n[ERROR] Backend is not healthy")
                print("Please start backend: cd backend && uvicorn app.main:app --port 8000")
                return 1
        except Exception as e:
            print(f"\n[ERROR] Cannot connect to backend: {e}")
            print("Please start backend: cd backend && uvicorn app.main:app --port 8000")
            return 1

        result = TestResult()

        # Determine which tests to run
        test_filter = sys.argv[1] if len(sys.argv) > 1 else "all"

        if test_filter in ["all", "health"]:
            await test_health(client, result)

        if test_filter in ["all", "auth"]:
            await test_auth(client, result)

        if test_filter in ["all", "upload"]:
            await test_upload(client, result)

        if test_filter in ["all", "proxy", "file_proxy"]:
            await test_file_proxy(client, result)

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
