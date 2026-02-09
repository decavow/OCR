"""
Test MinIO Storage Client.
Requires MinIO to be running (docker-compose -f docker-compose.infra.yml up -d minio)
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

# Override settings for testing
import os
os.environ["MINIO_ENDPOINT"] = "localhost:9000"
os.environ["MINIO_ACCESS_KEY"] = "minioadmin"
os.environ["MINIO_SECRET_KEY"] = "minioadmin"
os.environ["MINIO_SECURE"] = "false"


def test_storage_client():
    """Test MinIO storage operations."""
    from app.infrastructure.storage import (
        MinIOStorageService,
        ObjectNotFoundError,
        generate_object_key,
        parse_object_key,
    )

    print("\n=== MinIO Storage Client Tests ===\n")
    results = []

    # Create client
    storage = MinIOStorageService(
        endpoint="localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        secure=False,
    )

    test_bucket = "test-bucket"
    test_key = "test/file.txt"
    test_data = b"Hello, MinIO!"

    async def run_tests():
        # Test 1: Create bucket
        print("Test 1: Ensure buckets exist...")
        try:
            # Create test bucket
            if not await storage.bucket_exists(test_bucket):
                storage.client.make_bucket(test_bucket)
            await storage.ensure_buckets()
            print("  [OK] Buckets created/verified")
            results.append(("Ensure buckets", True))
        except Exception as e:
            print(f"  [FAIL] {e}")
            results.append(("Ensure buckets", False))

        # Test 2: Upload
        print("\nTest 2: Upload object...")
        try:
            await storage.upload(
                test_bucket,
                test_key,
                test_data,
                "text/plain",
            )
            print(f"  [OK] Uploaded {len(test_data)} bytes to {test_bucket}/{test_key}")
            results.append(("Upload", True))
        except Exception as e:
            print(f"  [FAIL] {e}")
            results.append(("Upload", False))

        # Test 3: Exists
        print("\nTest 3: Check object exists...")
        try:
            exists = await storage.exists(test_bucket, test_key)
            if exists:
                print(f"  [OK] Object exists")
                results.append(("Exists", True))
            else:
                print(f"  [FAIL] Object should exist")
                results.append(("Exists", False))
        except Exception as e:
            print(f"  [FAIL] {e}")
            results.append(("Exists", False))

        # Test 4: Get object info
        print("\nTest 4: Get object info...")
        try:
            info = await storage.get_object_info(test_bucket, test_key)
            print(f"  - Size: {info.size} bytes")
            print(f"  - Content-Type: {info.content_type}")
            print(f"  - ETag: {info.etag}")
            print(f"  [OK] Got object info")
            results.append(("Get info", True))
        except Exception as e:
            print(f"  [FAIL] {e}")
            results.append(("Get info", False))

        # Test 5: Download
        print("\nTest 5: Download object...")
        try:
            downloaded = await storage.download(test_bucket, test_key)
            if downloaded == test_data:
                print(f"  [OK] Downloaded and verified: {downloaded.decode()}")
                results.append(("Download", True))
            else:
                print(f"  [FAIL] Data mismatch")
                results.append(("Download", False))
        except Exception as e:
            print(f"  [FAIL] {e}")
            results.append(("Download", False))

        # Test 6: List objects
        print("\nTest 6: List objects...")
        try:
            objects = await storage.list_objects(test_bucket, prefix="test/")
            print(f"  Found {len(objects)} objects: {objects}")
            if test_key in objects:
                print(f"  [OK] Listed objects correctly")
                results.append(("List objects", True))
            else:
                print(f"  [FAIL] Expected object not in list")
                results.append(("List objects", False))
        except Exception as e:
            print(f"  [FAIL] {e}")
            results.append(("List objects", False))

        # Test 7: Presigned URL
        print("\nTest 7: Generate presigned URL...")
        try:
            url = await storage.get_presigned_url(test_bucket, test_key)
            print(f"  URL: {url[:80]}...")
            if url.startswith("http"):
                print(f"  [OK] Generated presigned URL")
                results.append(("Presigned URL", True))
            else:
                print(f"  [FAIL] Invalid URL format")
                results.append(("Presigned URL", False))
        except Exception as e:
            print(f"  [FAIL] {e}")
            results.append(("Presigned URL", False))

        # Test 8: Copy
        print("\nTest 8: Copy object...")
        copy_key = "test/file_copy.txt"
        try:
            await storage.copy(test_bucket, test_key, test_bucket, copy_key)
            exists = await storage.exists(test_bucket, copy_key)
            if exists:
                print(f"  [OK] Copied to {copy_key}")
                results.append(("Copy", True))
            else:
                print(f"  [FAIL] Copy not found")
                results.append(("Copy", False))
        except Exception as e:
            print(f"  [FAIL] {e}")
            results.append(("Copy", False))

        # Test 9: Move
        print("\nTest 9: Move object...")
        move_key = "test/file_moved.txt"
        try:
            await storage.move(test_bucket, copy_key, test_bucket, move_key)
            old_exists = await storage.exists(test_bucket, copy_key)
            new_exists = await storage.exists(test_bucket, move_key)
            if not old_exists and new_exists:
                print(f"  [OK] Moved to {move_key}")
                results.append(("Move", True))
            else:
                print(f"  [FAIL] Move failed (old={old_exists}, new={new_exists})")
                results.append(("Move", False))
        except Exception as e:
            print(f"  [FAIL] {e}")
            results.append(("Move", False))

        # Test 10: Delete
        print("\nTest 10: Delete object...")
        try:
            await storage.delete(test_bucket, move_key)
            exists = await storage.exists(test_bucket, move_key)
            if not exists:
                print(f"  [OK] Deleted {move_key}")
                results.append(("Delete", True))
            else:
                print(f"  [FAIL] Object still exists")
                results.append(("Delete", False))
        except Exception as e:
            print(f"  [FAIL] {e}")
            results.append(("Delete", False))

        # Test 11: Delete many
        print("\nTest 11: Delete many objects...")
        try:
            # Upload a few test objects
            for i in range(3):
                await storage.upload(
                    test_bucket,
                    f"test/bulk_{i}.txt",
                    f"data {i}".encode(),
                    "text/plain",
                )
            # Delete them
            await storage.delete_many(
                test_bucket,
                [f"test/bulk_{i}.txt" for i in range(3)],
            )
            # Verify
            remaining = await storage.list_objects(test_bucket, prefix="test/bulk_")
            if len(remaining) == 0:
                print(f"  [OK] Bulk delete successful")
                results.append(("Delete many", True))
            else:
                print(f"  [FAIL] Some objects remain: {remaining}")
                results.append(("Delete many", False))
        except Exception as e:
            print(f"  [FAIL] {e}")
            results.append(("Delete many", False))

        # Test 12: ObjectNotFoundError
        print("\nTest 12: ObjectNotFoundError on missing object...")
        try:
            await storage.download(test_bucket, "nonexistent/file.txt")
            print(f"  [FAIL] Should have raised ObjectNotFoundError")
            results.append(("NotFound error", False))
        except ObjectNotFoundError as e:
            print(f"  [OK] Correctly raised ObjectNotFoundError: {e}")
            results.append(("NotFound error", True))
        except Exception as e:
            print(f"  [FAIL] Wrong exception: {type(e).__name__}: {e}")
            results.append(("NotFound error", False))

        # Cleanup
        print("\nCleaning up test object...")
        try:
            await storage.delete(test_bucket, test_key)
        except Exception:
            pass

    asyncio.run(run_tests())

    # Test utils (synchronous)
    print("\nTest 13: Utility functions...")
    try:
        key = generate_object_key("user123", "req456", "file789", "document.pdf")
        expected = "user123/req456/file789/document.pdf"
        if key == expected:
            parsed = parse_object_key(key)
            if (parsed["user_id"] == "user123" and
                parsed["request_id"] == "req456" and
                parsed["file_id"] == "file789" and
                parsed["filename"] == "document.pdf"):
                print(f"  [OK] Utils working correctly")
                results.append(("Utils", True))
            else:
                print(f"  [FAIL] Parse failed: {parsed}")
                results.append(("Utils", False))
        else:
            print(f"  [FAIL] Key generation: {key} != {expected}")
            results.append(("Utils", False))
    except Exception as e:
        print(f"  [FAIL] {e}")
        results.append(("Utils", False))

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "[OK]" if result else "[FAIL]"
        print(f"  {status} {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n>>> All storage tests passed!")
        return 0
    else:
        print("\n>>> Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(test_storage_client())
