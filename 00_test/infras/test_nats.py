"""
NATS JetStream Infrastructure Test
Run: python test_nats.py
"""

import asyncio
import json
import sys
from datetime import datetime

import nats
from nats.errors import TimeoutError as NatsTimeoutError

# Configuration
NATS_URL = "nats://localhost:4222"
STREAM_NAME = "OCR_JOBS"
DLQ_STREAM_NAME = "OCR_DLQ"
TEST_SUBJECT = "ocr.ocr_text_raw.tier0"


async def test_connection():
    """Test: Can connect to NATS."""
    print("\n[TEST] Connection to NATS...")
    try:
        nc = await nats.connect(NATS_URL)
        print(f"  [OK] Connected to NATS server")
        print(f"    - Client ID: {nc.client_id}")
        print(f"    - Server: {nc.connected_url}")

        await nc.drain()
        return True
    except Exception as e:
        print(f"  [FAIL] Failed: {e}")
        return False


async def test_jetstream_enabled():
    """Test: JetStream is enabled."""
    print("\n[TEST] JetStream enabled...")
    try:
        nc = await nats.connect(NATS_URL)
        js = nc.jetstream()

        # Get JetStream account info
        account = await js.account_info()
        print(f"  [OK] JetStream is enabled")
        print(f"    - Memory: {account.memory / 1024 / 1024:.2f} MB used")
        print(f"    - Storage: {account.storage / 1024 / 1024:.2f} MB used")
        print(f"    - Streams: {account.streams}")

        await nc.drain()
        return True
    except Exception as e:
        print(f"  [FAIL] JetStream not available: {e}")
        return False


async def test_create_streams():
    """Test: Create required streams."""
    print("\n[TEST] Creating streams...")
    nc = await nats.connect(NATS_URL)
    js = nc.jetstream()

    streams = [
        (STREAM_NAME, ["ocr.>"]),
        (DLQ_STREAM_NAME, ["dlq.>"]),
    ]

    try:
        for stream_name, subjects in streams:
            try:
                # Try to get existing stream
                info = await js.stream_info(stream_name)
                print(f"  [OK] Stream exists: {stream_name}")
                print(f"    - Messages: {info.state.messages}")
                print(f"    - Subjects: {info.config.subjects}")
            except Exception:
                # Create new stream
                await js.add_stream(name=stream_name, subjects=subjects)
                print(f"  [OK] Created stream: {stream_name}")

        await nc.drain()
        return True
    except Exception as e:
        print(f"  [FAIL] Failed: {e}")
        await nc.drain()
        return False


async def test_publish_consume():
    """Test: Publish and consume message."""
    print("\n[TEST] Publish/Consume message...")
    nc = await nats.connect(NATS_URL)
    js = nc.jetstream()

    test_message = {
        "job_id": "test-job-001",
        "file_id": "test-file-001",
        "method": "ocr_text_raw",
        "tier": 0,
        "timestamp": datetime.now().isoformat(),
    }

    try:
        # Publish
        ack = await js.publish(
            TEST_SUBJECT,
            json.dumps(test_message).encode(),
        )
        print(f"  [OK] Published message to {TEST_SUBJECT}")
        print(f"    - Stream: {ack.stream}")
        print(f"    - Sequence: {ack.seq}")

        # Create pull subscriber directly (simpler API)
        consumer_name = "test-consumer-" + str(ack.seq)
        sub = await js.pull_subscribe(
            TEST_SUBJECT,
            durable=consumer_name,
            stream=STREAM_NAME,
        )

        # Pull message
        msgs = await sub.fetch(1, timeout=5)

        if msgs:
            msg = msgs[0]
            received = json.loads(msg.data.decode())
            print(f"  [OK] Received message")
            print(f"    - Job ID: {received['job_id']}")

            # Acknowledge
            await msg.ack()
            print(f"  [OK] Message acknowledged")

        await nc.drain()
        return True
    except Exception as e:
        print(f"  [FAIL] Failed: {e}")
        try:
            await nc.drain()
        except Exception:
            pass
        return False


async def test_http_monitoring():
    """Test: HTTP monitoring endpoint."""
    print("\n[TEST] HTTP Monitoring...")
    try:
        import httpx

        async with httpx.AsyncClient() as client:
            # Health check
            response = await client.get("http://localhost:8222/healthz")
            print(f"  [OK] Health endpoint: {response.status_code}")

            # Server info
            response = await client.get("http://localhost:8222/varz")
            if response.status_code == 200:
                info = response.json()
                print(f"  [OK] Server info retrieved")
                print(f"    - Version: {info.get('version', 'unknown')}")
                print(f"    - Uptime: {info.get('uptime', 'unknown')}")

            # JetStream info
            response = await client.get("http://localhost:8222/jsz")
            if response.status_code == 200:
                js_info = response.json()
                print(f"  [OK] JetStream info retrieved")
                print(f"    - Streams: {js_info.get('streams', 0)}")

        return True
    except Exception as e:
        print(f"  [FAIL] Failed: {e}")
        return False


async def run_tests():
    """Run all tests."""
    print("=" * 60)
    print("NATS JetStream Infrastructure Test")
    print("=" * 60)
    print(f"URL: {NATS_URL}")

    tests = [
        ("Connection", test_connection),
        ("JetStream Enabled", test_jetstream_enabled),
        ("Create Streams", test_create_streams),
        ("Publish/Consume", test_publish_consume),
        ("HTTP Monitoring", test_http_monitoring),
    ]

    results = []
    for name, test_fn in tests:
        try:
            result = await test_fn()
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
        print("\n>>> All NATS tests passed!")
        return 0
    else:
        print("\n>>> Some tests failed!")
        return 1


def main():
    return asyncio.run(run_tests())


if __name__ == "__main__":
    sys.exit(main())
