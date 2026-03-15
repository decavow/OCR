"""Worker unit test fixtures.

Provides shared fixtures for all worker unit tests:
- sys.path setup for importing worker modules
- Mock factories for clients (queue, file_proxy, orchestrator, heartbeat)
- Sample data fixtures
"""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock

import pytest

# Add worker source to sys.path
WORKER_ROOT = Path(__file__).parent.parent.parent / "03_worker"
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))


# ---------------------------------------------------------------------------
# Async event loop
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Mock factories
# ---------------------------------------------------------------------------

def make_queue_mock():
    q = MagicMock()
    q.connect = AsyncMock()
    q.disconnect = AsyncMock()
    q.pull_job = AsyncMock(return_value=None)
    q.ack = AsyncMock()
    q.nak = AsyncMock()
    q.term = AsyncMock()
    return q


def make_file_proxy_mock():
    proxy = MagicMock()
    proxy.download = AsyncMock(return_value=(b"fake image content", "image/png", "test.png"))
    proxy.upload = AsyncMock(return_value="result/key/path")
    proxy.set_access_key = MagicMock()
    proxy.has_access_key = True
    return proxy


def make_orchestrator_mock():
    orch = MagicMock()
    orch.register = AsyncMock(return_value={
        "type_status": "APPROVED",
        "instance_status": "ACTIVE",
        "access_key": "sk_test_key",
    })
    orch.deregister = AsyncMock()
    orch.update_status = AsyncMock()
    orch.set_access_key = MagicMock()
    orch.has_access_key = True
    return orch


def make_heartbeat_mock():
    hb = MagicMock()
    hb.start = AsyncMock()
    hb.stop = AsyncMock()
    hb.set_state = MagicMock()
    hb.set_action_callback = MagicMock()
    hb.set_access_key = MagicMock()
    return hb


def make_job_dict(job_id="job-1", file_id="file-1", method="ocr_paddle_text"):
    return {
        "job_id": job_id,
        "file_id": file_id,
        "request_id": "req-1",
        "method": method,
        "tier": 0,
        "output_format": "txt",
        "object_key": "user1/req1/file1/test.png",
        "_msg_id": "msg-1",
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def shutdown_handler():
    """GracefulShutdown mock."""
    handler = MagicMock()
    handler.is_shutting_down = False
    return handler


@pytest.fixture
def job_dict():
    """Standard job message dict."""
    return make_job_dict()


@pytest.fixture
def sample_png():
    """Minimal valid PNG (1x1 transparent pixel)."""
    return (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )


@pytest.fixture
def sample_pdf():
    """Minimal valid PDF bytes."""
    return (
        b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
        b"0000000052 00000 n \n0000000101 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF"
    )


@pytest.fixture
def rgb_image_array():
    """Simple 100x100 RGB numpy array."""
    import numpy as np
    return np.zeros((100, 100, 3), dtype=np.uint8)


@pytest.fixture
def grayscale_image_array():
    """Simple 100x100 grayscale numpy array."""
    import numpy as np
    return np.zeros((100, 100), dtype=np.uint8)
