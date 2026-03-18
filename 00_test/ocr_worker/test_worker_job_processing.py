"""Phase D — OCRWorker job processing tests (mock all clients).

Tests WJ-001 through WJ-021: process_job happy path, error handling,
_handle_failure, and run loop behavior.
"""

import asyncio
import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch, call

import httpx
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
        MockProcessor.return_value.process = AsyncMock(return_value=b"OCR output text")
        MockProcessor.return_value.get_engine_info = MagicMock(return_value={
            "engine": "paddleocr", "version": "2.7.3",
        })

        from app.core.worker import OCRWorker
        worker = OCRWorker(shutdown_handler)

    return worker, mock_settings


# ---------------------------------------------------------------------------
# Phase D.3: process_job happy path
# ---------------------------------------------------------------------------

class TestProcessJobHappyPath:
    """WJ-001 to WJ-008: process_job succeeds end to end."""

    # WJ-001: state.start_job called with job_id
    @pytest.mark.asyncio
    async def test_start_job_called(self):
        worker, _ = _make_worker()
        worker.state = MagicMock()
        job = make_job_dict(job_id="j-1")

        await worker.process_job(job)

        worker.state.start_job.assert_called_once_with("j-1")

    # WJ-002: orchestrator.update_status("PROCESSING") called first
    @pytest.mark.asyncio
    async def test_update_processing(self):
        worker, _ = _make_worker()
        worker.state = MagicMock()
        job = make_job_dict()

        await worker.process_job(job)

        calls = worker.orchestrator.update_status.call_args_list
        assert calls[0] == call("job-1", "PROCESSING")

    # WJ-003: file_proxy.download called with job_id and file_id
    @pytest.mark.asyncio
    async def test_download_called(self):
        worker, _ = _make_worker()
        worker.state = MagicMock()
        job = make_job_dict(job_id="j-1", file_id="f-1")

        await worker.process_job(job)

        worker.file_proxy.download.assert_awaited_once_with("j-1", "f-1")

    # WJ-004: processor.process called with content, format, method
    @pytest.mark.asyncio
    async def test_processor_called(self):
        worker, _ = _make_worker()
        worker.state = MagicMock()
        worker.file_proxy.download = AsyncMock(
            return_value=(b"image data", "image/png", "test.png")
        )
        job = make_job_dict(method="ocr_paddle_text")
        job["output_format"] = "txt"

        await worker.process_job(job)

        worker.processor.process.assert_awaited_once_with(
            file_content=b"image data",
            output_format="txt",
            method="ocr_paddle_text",
        )

    # WJ-005: file_proxy.upload called with result
    @pytest.mark.asyncio
    async def test_upload_called(self):
        worker, _ = _make_worker()
        worker.state = MagicMock()
        worker.processor.process = AsyncMock(return_value=b"result text")
        job = make_job_dict()

        await worker.process_job(job)

        worker.file_proxy.upload.assert_awaited_once()
        call_kwargs = worker.file_proxy.upload.call_args.kwargs
        assert call_kwargs["job_id"] == "job-1"
        assert call_kwargs["file_id"] == "file-1"
        assert call_kwargs["content"] == b"result text"

    # WJ-006: content_type mapping txt -> text/plain
    @pytest.mark.asyncio
    async def test_content_type_txt(self):
        worker, _ = _make_worker()
        worker.state = MagicMock()
        job = make_job_dict()
        job["output_format"] = "txt"

        await worker.process_job(job)

        call_kwargs = worker.file_proxy.upload.call_args.kwargs
        assert call_kwargs["content_type"] == "text/plain"

    # WJ-007: content_type mapping json -> application/json
    @pytest.mark.asyncio
    async def test_content_type_json(self):
        worker, _ = _make_worker()
        worker.state = MagicMock()
        job = make_job_dict()
        job["output_format"] = "json"

        await worker.process_job(job)

        call_kwargs = worker.file_proxy.upload.call_args.kwargs
        assert call_kwargs["content_type"] == "application/json"

    # WJ-008: queue.ack called on success
    @pytest.mark.asyncio
    async def test_ack_on_success(self):
        worker, _ = _make_worker()
        worker.state = MagicMock()
        job = make_job_dict()

        await worker.process_job(job)

        worker.queue.ack.assert_awaited_once_with("msg-1")


class TestProcessJobErrors:
    """WJ-009 to WJ-012: process_job error handling."""

    # WJ-009: state.end_job called in finally (success)
    @pytest.mark.asyncio
    async def test_end_job_on_success(self):
        worker, _ = _make_worker()
        worker.state = MagicMock()
        job = make_job_dict()

        await worker.process_job(job)

        worker.state.end_job.assert_called_once()

    # WJ-010: state.end_job called in finally (failure)
    @pytest.mark.asyncio
    async def test_end_job_on_failure(self):
        worker, _ = _make_worker()
        worker.state = MagicMock()
        worker.file_proxy.download = AsyncMock(side_effect=Exception("download failed"))
        job = make_job_dict()

        await worker.process_job(job)

        worker.state.end_job.assert_called_once()

    # WJ-011: RetriableError triggers _handle_failure with retriable=True
    @pytest.mark.asyncio
    async def test_retriable_error(self):
        worker, _ = _make_worker()
        worker.state = MagicMock()

        from app.utils.errors import RetriableError
        worker.file_proxy.download = AsyncMock(
            side_effect=RetriableError("temp failure")
        )
        job = make_job_dict()

        await worker.process_job(job)

        # Should nak (retry)
        worker.queue.nak.assert_awaited_once()

    # WJ-012: PermanentError triggers _handle_failure with retriable=False
    @pytest.mark.asyncio
    async def test_permanent_error(self):
        worker, _ = _make_worker()
        worker.state = MagicMock()

        from app.utils.errors import PermanentError
        worker.file_proxy.download = AsyncMock(
            side_effect=PermanentError("bad image")
        )
        job = make_job_dict()

        await worker.process_job(job)

        # Should term (no retry)
        worker.queue.term.assert_awaited_once()


class TestProcessJobContentTypes:
    """Additional content type tests."""

    # WJ-extra: content_type mapping md -> text/markdown
    @pytest.mark.asyncio
    async def test_content_type_md(self):
        worker, _ = _make_worker()
        worker.state = MagicMock()
        job = make_job_dict()
        job["output_format"] = "md"

        await worker.process_job(job)

        call_kwargs = worker.file_proxy.upload.call_args.kwargs
        assert call_kwargs["content_type"] == "text/markdown"

    # WJ-extra: content_type mapping html -> text/html
    @pytest.mark.asyncio
    async def test_content_type_html(self):
        worker, _ = _make_worker()
        worker.state = MagicMock()
        job = make_job_dict()
        job["output_format"] = "html"

        await worker.process_job(job)

        call_kwargs = worker.file_proxy.upload.call_args.kwargs
        assert call_kwargs["content_type"] == "text/html"


class TestHandleFailure:
    """WJ-013 to WJ-016: _handle_failure."""

    # WJ-013: reports FAILED status to orchestrator
    @pytest.mark.asyncio
    async def test_reports_failed(self):
        worker, _ = _make_worker()
        error = Exception("something broke")

        await worker._handle_failure("j-1", "msg-1", error, retriable=True)

        worker.orchestrator.update_status.assert_awaited_once_with(
            job_id="j-1",
            status="FAILED",
            error="something broke",
            retriable=True,
        )

    # WJ-014: retriable=True naks with delay
    @pytest.mark.asyncio
    async def test_retriable_naks(self):
        worker, _ = _make_worker()
        error = Exception("temp")

        await worker._handle_failure("j-1", "msg-1", error, retriable=True)

        worker.queue.nak.assert_awaited_once_with("msg-1", delay=5.0)

    # WJ-015: retriable=False terminates message
    @pytest.mark.asyncio
    async def test_non_retriable_terms(self):
        worker, _ = _make_worker()
        error = Exception("permanent")

        await worker._handle_failure("j-1", "msg-1", error, retriable=False)

        worker.queue.term.assert_awaited_once_with("msg-1")

    # WJ-016: 404 from orchestrator -> term (job not found)
    @pytest.mark.asyncio
    async def test_job_not_found_terminates(self):
        worker, _ = _make_worker()

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        worker.orchestrator.update_status = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                message="Not Found",
                request=MagicMock(),
                response=mock_resp,
            )
        )

        await worker._handle_failure("j-1", "msg-1", Exception("err"), retriable=True)

        worker.queue.term.assert_awaited_once_with("msg-1")

    # WJ-022: record_error() called on failure
    @pytest.mark.asyncio
    async def test_record_error_called(self):
        worker, _ = _make_worker()
        worker.state = MagicMock()
        error = Exception("something broke")

        await worker._handle_failure("j-1", "msg-1", error, retriable=True)

        worker.state.record_error.assert_called_once()

    # WJ-023: record_error increments error_count in heartbeat
    @pytest.mark.asyncio
    async def test_record_error_increments_count(self):
        from app.core.state import WorkerState
        worker, _ = _make_worker()
        worker.state = WorkerState()

        await worker._handle_failure("j-1", "msg-1", Exception("err1"), retriable=True)
        assert worker.state.error_count == 1

        await worker._handle_failure("j-2", "msg-2", Exception("err2"), retriable=False)
        assert worker.state.error_count == 2

    # WJ-024: record_error called even when orchestrator returns 404
    @pytest.mark.asyncio
    async def test_record_error_on_job_not_found(self):
        worker, _ = _make_worker()
        worker.state = MagicMock()

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        worker.orchestrator.update_status = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                message="Not Found",
                request=MagicMock(),
                response=mock_resp,
            )
        )

        await worker._handle_failure("j-1", "msg-1", Exception("err"), retriable=True)

        worker.state.record_error.assert_called_once()

    # WJ-025: error_count reflected in heartbeat payload
    @pytest.mark.asyncio
    async def test_error_count_in_heartbeat_payload(self):
        from app.core.state import WorkerState
        worker, _ = _make_worker()
        worker.state = WorkerState()

        await worker._handle_failure("j-1", "msg-1", Exception("err"), retriable=True)

        heartbeat = worker.state.to_heartbeat()
        assert heartbeat["error_count"] == 1


class TestRunLoop:
    """WJ-017 to WJ-021: run loop behavior."""

    # WJ-017: run exits when shutdown flag is set
    @pytest.mark.asyncio
    async def test_run_exits_on_shutdown(self):
        shutdown = MagicMock()
        shutdown.is_shutting_down = True
        worker, _ = _make_worker(shutdown_handler=shutdown)

        # Should return immediately
        await worker.run()

        worker.queue.pull_job.assert_not_awaited()

    # WJ-018: run sleeps when not approved
    @pytest.mark.asyncio
    async def test_run_sleeps_not_approved(self):
        shutdown = MagicMock()
        # Shut down after first iteration
        shutdown.is_shutting_down = False
        call_count = 0

        def toggle_shutdown(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                shutdown.is_shutting_down = True

        worker, _ = _make_worker(shutdown_handler=shutdown)
        worker.is_approved = False

        with patch("app.core.worker.asyncio.sleep", new_callable=AsyncMock, side_effect=toggle_shutdown):
            await worker.run()

        worker.queue.pull_job.assert_not_awaited()

    # WJ-019: run sleeps when draining
    @pytest.mark.asyncio
    async def test_run_sleeps_draining(self):
        shutdown = MagicMock()
        shutdown.is_shutting_down = False

        def stop(*args, **kwargs):
            shutdown.is_shutting_down = True

        worker, _ = _make_worker(shutdown_handler=shutdown)
        worker.is_approved = True
        worker.is_draining = True

        with patch("app.core.worker.asyncio.sleep", new_callable=AsyncMock, side_effect=stop):
            await worker.run()

        worker.queue.pull_job.assert_not_awaited()

    # WJ-020: run pulls job and processes when approved
    @pytest.mark.asyncio
    async def test_run_processes_job(self):
        shutdown = MagicMock()
        shutdown.is_shutting_down = False

        job = make_job_dict()

        call_count = 0

        async def pull_job_side_effect(timeout=5.0):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return job
            # Second call: stop
            shutdown.is_shutting_down = True
            return None

        worker, _ = _make_worker(shutdown_handler=shutdown)
        worker.is_approved = True
        worker.queue.pull_job = AsyncMock(side_effect=pull_job_side_effect)
        worker.process_job = AsyncMock()

        await worker.run()

        worker.process_job.assert_awaited_once_with(job)

    # WJ-021: run continues polling when no job available
    @pytest.mark.asyncio
    async def test_run_continues_on_no_job(self):
        shutdown = MagicMock()
        shutdown.is_shutting_down = False

        call_count = 0

        async def pull_job_side_effect(timeout=5.0):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                shutdown.is_shutting_down = True
            return None

        worker, _ = _make_worker(shutdown_handler=shutdown)
        worker.is_approved = True
        worker.queue.pull_job = AsyncMock(side_effect=pull_job_side_effect)
        worker.process_job = AsyncMock()

        await worker.run()

        # pull_job called at least twice, process_job never called
        assert worker.queue.pull_job.await_count >= 2
        worker.process_job.assert_not_awaited()
