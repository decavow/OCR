"""Phase D — OCRWorker lifecycle tests (mock all clients).

Tests WL-001 through WL-011: start, _set_access_key, stop,
_handle_heartbeat_action, and _graceful_shutdown.
"""

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Install mock nats modules before any worker imports
# ---------------------------------------------------------------------------

def _ensure_nats_mocks():
    if "nats" not in sys.modules:
        nats_mod = ModuleType("nats")
        nats_mod.connect = AsyncMock()
        nats_errors = ModuleType("nats.errors")
        nats_errors.TimeoutError = type("TimeoutError", (Exception,), {})
        nats_mod.errors = nats_errors
        nats_js = ModuleType("nats.js")
        nats_js.JetStreamContext = MagicMock
        nats_js_api = ModuleType("nats.js.api")
        nats_js_api.ConsumerConfig = MagicMock
        nats_js_api.DeliverPolicy = MagicMock
        nats_js_api.AckPolicy = MagicMock
        sys.modules["nats"] = nats_mod
        sys.modules["nats.errors"] = nats_errors
        sys.modules["nats.js"] = nats_js
        sys.modules["nats.js.api"] = nats_js_api

_ensure_nats_mocks()


# ---------------------------------------------------------------------------
# Inline mock factories (same as conftest.py but importable directly)
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_worker(shutdown_handler=None, access_key=None):
    """Create an OCRWorker with all clients replaced by mocks."""
    if shutdown_handler is None:
        shutdown_handler = MagicMock()
        shutdown_handler.is_shutting_down = False

    mock_settings = MagicMock()
    mock_settings.worker_instance_id = "worker-test-1"
    mock_settings.worker_service_type = "ocr-text-tier0"
    mock_settings.worker_filter_subject = "ocr.ocr_paddle_text.tier0"
    mock_settings.worker_display_name = "Test Worker"
    mock_settings.worker_description = "Test"
    mock_settings.worker_allowed_methods = ["ocr_paddle_text"]
    mock_settings.worker_allowed_tiers = [0]
    mock_settings.worker_dev_contact = None
    mock_settings.worker_supported_formats = ["txt", "json"]
    mock_settings.worker_access_key = access_key

    with patch("app.core.worker.settings", mock_settings), \
         patch("app.core.worker.OCRProcessor") as MockProcessor, \
         patch("app.core.worker.QueueClient", return_value=make_queue_mock()), \
         patch("app.core.worker.FileProxyClient", return_value=make_file_proxy_mock()), \
         patch("app.core.worker.OrchestratorClient", return_value=make_orchestrator_mock()), \
         patch("app.core.worker.HeartbeatClient", return_value=make_heartbeat_mock()):

        MockProcessor.return_value = MagicMock()
        MockProcessor.return_value.get_engine_info = MagicMock(return_value={
            "engine": "paddleocr", "version": "2.7.3",
        })

        from app.core.worker import OCRWorker
        worker = OCRWorker(shutdown_handler)

    return worker, mock_settings


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestWorkerStart:
    """WL-001 to WL-003: start."""

    # WL-001: start registers and sets access key on approval
    @pytest.mark.asyncio
    async def test_start_approved(self):
        worker, settings = _make_worker()
        worker.orchestrator.register = AsyncMock(return_value={
            "type_status": "APPROVED",
            "instance_status": "ACTIVE",
            "access_key": "sk_approved",
        })

        with patch("app.core.worker.settings", settings):
            await worker.start()

        worker.orchestrator.register.assert_awaited_once()
        worker.queue.connect.assert_awaited_once()
        worker.heartbeat.start.assert_awaited_once()
        assert worker.is_approved is True
        assert worker._access_key == "sk_approved"

    # WL-002: start with REJECTED triggers shutdown
    @pytest.mark.asyncio
    async def test_start_rejected(self):
        shutdown = MagicMock()
        shutdown.is_shutting_down = False
        worker, settings = _make_worker(shutdown_handler=shutdown)
        worker.orchestrator.register = AsyncMock(return_value={
            "type_status": "REJECTED",
            "instance_status": "INACTIVE",
        })

        with patch("app.core.worker.settings", settings):
            await worker.start()

        assert shutdown.is_shutting_down is True

    # WL-003: start with PENDING waits for approval
    @pytest.mark.asyncio
    async def test_start_pending(self):
        worker, settings = _make_worker()
        worker.orchestrator.register = AsyncMock(return_value={
            "type_status": "PENDING",
            "instance_status": "ACTIVE",
        })

        with patch("app.core.worker.settings", settings):
            await worker.start()

        assert worker.is_approved is False
        # Queue and heartbeat still started
        worker.queue.connect.assert_awaited_once()
        worker.heartbeat.start.assert_awaited_once()


class TestWorkerSetAccessKey:
    """WL-004: _set_access_key."""

    # WL-004: sets key on worker and all clients
    def test_set_access_key(self):
        worker, _ = _make_worker()
        assert worker.is_approved is False

        worker._set_access_key("sk_new")

        assert worker._access_key == "sk_new"
        assert worker.is_approved is True
        worker.orchestrator.set_access_key.assert_called_once_with("sk_new")
        worker.file_proxy.set_access_key.assert_called_once_with("sk_new")
        worker.heartbeat.set_access_key.assert_called_once_with("sk_new")


class TestWorkerStop:
    """WL-005 to WL-006: stop."""

    # WL-005: stop cleans up heartbeat, queue, deregister
    @pytest.mark.asyncio
    async def test_stop_cleanup(self):
        worker, settings = _make_worker()

        with patch("app.core.worker.settings", settings):
            await worker.stop()

        worker.heartbeat.stop.assert_awaited_once()
        worker.queue.disconnect.assert_awaited_once()
        worker.orchestrator.deregister.assert_awaited_once_with("worker-test-1")

    # WL-006: stop swallows deregister errors
    @pytest.mark.asyncio
    async def test_stop_deregister_error_swallowed(self):
        worker, settings = _make_worker()
        worker.orchestrator.deregister = AsyncMock(
            side_effect=ConnectionError("offline")
        )

        with patch("app.core.worker.settings", settings):
            # Should not raise
            await worker.stop()

        worker.heartbeat.stop.assert_awaited_once()
        worker.queue.disconnect.assert_awaited_once()


class TestWorkerHeartbeatAction:
    """WL-007 to WL-010: _handle_heartbeat_action."""

    # WL-007: action=continue does nothing
    @pytest.mark.asyncio
    async def test_action_continue(self):
        worker, _ = _make_worker()
        initial_approved = worker.is_approved
        initial_draining = worker.is_draining

        await worker._handle_heartbeat_action({"action": "continue"})

        assert worker.is_approved == initial_approved
        assert worker.is_draining == initial_draining

    # WL-008: action=approved sets access key
    @pytest.mark.asyncio
    async def test_action_approved(self):
        worker, _ = _make_worker()
        assert worker.is_approved is False

        await worker._handle_heartbeat_action({
            "action": "approved",
            "access_key": "sk_via_heartbeat",
        })

        assert worker.is_approved is True
        assert worker._access_key == "sk_via_heartbeat"

    # WL-009: action=drain sets draining flag
    @pytest.mark.asyncio
    async def test_action_drain(self):
        worker, _ = _make_worker()
        assert worker.is_draining is False

        await worker._handle_heartbeat_action({"action": "drain"})

        assert worker.is_draining is True

    # WL-010: action=shutdown triggers graceful shutdown
    @pytest.mark.asyncio
    async def test_action_shutdown(self):
        shutdown = MagicMock()
        shutdown.is_shutting_down = False
        worker, settings = _make_worker(shutdown_handler=shutdown)

        with patch("app.core.worker.settings", settings):
            await worker._handle_heartbeat_action({
                "action": "shutdown",
                "rejection_reason": "type rejected",
            })

        assert shutdown.is_shutting_down is True
        worker.orchestrator.deregister.assert_awaited_once()


class TestWorkerReRegistration:
    """WL-012 to WL-015: re-registration on heartbeat 404."""

    # WL-012: action=re_register calls _register and re-approves
    @pytest.mark.asyncio
    async def test_action_re_register_approved(self):
        worker, settings = _make_worker()
        worker.orchestrator.register = AsyncMock(return_value={
            "type_status": "APPROVED",
            "instance_status": "ACTIVE",
            "access_key": "sk_re_registered",
        })

        with patch("app.core.worker.settings", settings):
            await worker._handle_heartbeat_action({"action": "re_register"})

        worker.orchestrator.register.assert_awaited_once()
        assert worker.is_approved is True
        assert worker._access_key == "sk_re_registered"
        assert worker._re_register_attempts == 0

    # WL-013: action=re_register with REJECTED triggers shutdown
    @pytest.mark.asyncio
    async def test_action_re_register_rejected(self):
        shutdown = MagicMock()
        shutdown.is_shutting_down = False
        worker, settings = _make_worker(shutdown_handler=shutdown)
        worker.orchestrator.register = AsyncMock(return_value={
            "type_status": "REJECTED",
            "instance_status": "INACTIVE",
        })

        with patch("app.core.worker.settings", settings):
            await worker._handle_heartbeat_action({"action": "re_register"})

        assert shutdown.is_shutting_down is True

    # WL-014: action=re_register with PENDING sets is_approved=False
    @pytest.mark.asyncio
    async def test_action_re_register_pending(self):
        worker, settings = _make_worker(access_key="sk_old")
        worker.orchestrator.register = AsyncMock(return_value={
            "type_status": "PENDING",
            "instance_status": "WAITING",
        })

        with patch("app.core.worker.settings", settings):
            await worker._handle_heartbeat_action({"action": "re_register"})

        assert worker.is_approved is False
        assert worker._re_register_attempts == 0

    # WL-015: re_register failure is handled gracefully
    @pytest.mark.asyncio
    async def test_action_re_register_failure(self):
        worker, settings = _make_worker()
        worker.orchestrator.register = AsyncMock(
            side_effect=ConnectionError("backend unreachable")
        )

        with patch("app.core.worker.settings", settings):
            # Should not raise
            await worker._handle_heartbeat_action({"action": "re_register"})

        assert worker._re_register_attempts == 1

    # WL-016: successful heartbeat resets re_register_attempts counter
    @pytest.mark.asyncio
    async def test_continue_resets_re_register_counter(self):
        worker, _ = _make_worker()
        worker._re_register_attempts = 5

        await worker._handle_heartbeat_action({"action": "continue"})

        assert worker._re_register_attempts == 0


class TestWorkerGracefulShutdown:
    """WL-017: _graceful_shutdown."""

    # WL-017: deregisters and sets shutdown flag
    @pytest.mark.asyncio
    async def test_graceful_shutdown(self):
        shutdown = MagicMock()
        shutdown.is_shutting_down = False
        worker, settings = _make_worker(shutdown_handler=shutdown)

        with patch("app.core.worker.settings", settings):
            await worker._graceful_shutdown()

        worker.orchestrator.deregister.assert_awaited_once_with("worker-test-1")
        assert shutdown.is_shutting_down is True
