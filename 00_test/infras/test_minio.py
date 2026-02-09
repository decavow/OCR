"""
MinIO Infrastructure Test
Run: python test_minio.py
"""

from minio import Minio
from minio.error import S3Error
from io import BytesIO
import sys

# Configuration
MINIO_ENDPOINT = "localhost:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"
MINIO_SECURE = False

TEST_BUCKETS = ["uploads", "results", "deleted"]


def create_client() -> Minio:
    """Create MinIO client."""
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE,
    )


def test_connection():
    """Test: Can connect to MinIO."""
    print("\n[TEST] Connection to MinIO...")
    try:
        client = create_client()
        # Try listing buckets to verify connection
        buckets = client.list_buckets()
        print(f"  [OK] Connected! Found {len(buckets)} existing buckets")
        return True
    except Exception as e:
        print(f"  [FAIL] Failed: {e}")
        return False


def test_create_buckets():
    """Test: Create required buckets."""
    print("\n[TEST] Creating buckets...")
    client = create_client()

    for bucket in TEST_BUCKETS:
        try:
            if not client.bucket_exists(bucket):
                client.make_bucket(bucket)
                print(f"  [OK] Created bucket: {bucket}")
            else:
                print(f"  [OK] Bucket exists: {bucket}")
        except S3Error as e:
            print(f"  [FAIL] Failed to create {bucket}: {e}")
            return False
    return True


def test_upload_download():
    """Test: Upload and download file."""
    print("\n[TEST] Upload/Download file...")
    client = create_client()

    bucket = "uploads"
    object_name = "test/hello.txt"
    test_content = b"Hello from OCR Platform test!"

    try:
        # Upload
        client.put_object(
            bucket,
            object_name,
            BytesIO(test_content),
            len(test_content),
            content_type="text/plain",
        )
        print(f"  [OK] Uploaded: {object_name}")

        # Download
        response = client.get_object(bucket, object_name)
        downloaded = response.read()
        response.close()
        response.release_conn()

        if downloaded == test_content:
            print(f"  [OK] Downloaded and verified content")
        else:
            print(f"  [FAIL] Content mismatch!")
            return False

        # Cleanup
        client.remove_object(bucket, object_name)
        print(f"  [OK] Cleaned up test file")

        return True
    except S3Error as e:
        print(f"  [FAIL] Failed: {e}")
        return False


def test_presigned_url():
    """Test: Generate presigned URL."""
    print("\n[TEST] Presigned URL...")
    client = create_client()

    bucket = "uploads"
    object_name = "test/presign-test.txt"
    test_content = b"Presigned URL test content"

    try:
        # Upload test file
        client.put_object(
            bucket,
            object_name,
            BytesIO(test_content),
            len(test_content),
        )

        # Generate presigned URL
        from datetime import timedelta
        url = client.presigned_get_object(bucket, object_name, expires=timedelta(hours=1))
        print(f"  [OK] Generated presigned URL: {url[:60]}...")

        # Cleanup
        client.remove_object(bucket, object_name)
        print(f"  [OK] Cleaned up test file")

        return True
    except S3Error as e:
        print(f"  [FAIL] Failed: {e}")
        return False


def main():
    print("=" * 60)
    print("MinIO Infrastructure Test")
    print("=" * 60)
    print(f"Endpoint: {MINIO_ENDPOINT}")

    tests = [
        ("Connection", test_connection),
        ("Create Buckets", test_create_buckets),
        ("Upload/Download", test_upload_download),
        ("Presigned URL", test_presigned_url),
    ]

    results = []
    for name, test_fn in tests:
        try:
            result = test_fn()
            results.append((name, result))
        except Exception as e:
            print(f"  [FAIL] Unexpected error: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n>>> All MinIO tests passed!")
        return 0
    else:
        print("\n>>> Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
