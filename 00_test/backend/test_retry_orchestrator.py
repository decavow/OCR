"""Unit tests for RetryOrchestrator (02_backend/app/modules/job/orchestrator.py).

Service-layer tests with mocked repositories and queue.

Test IDs: RO-001 to RO-015
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BACKEND_ROOT = Path(__file__).parent.parent.parent / "02_backend"
TEST_DIR = Path(__file__).parent

sys.path.insert(0, str(TEST_DIR))
from conftest import make_job, make_file
sys.path.pop(0)


# ---------------------------------------------------------------------------
# Load real helper modules (no app deps)
# ---------------------------------------------------------------------------

def _load_messages():
    mod_path = BACKEND_ROOT / "app" / "infrastructure" / "queue" / "messages.py"
    spec = importlib.util.spec_from_file_location("messages", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_subjects():
    mod_path = BACKEND_ROOT / "app" / "infrastructure" / "queue" / "subjects.py"
    spec = importlib.util.spec_from_file_location("subjects", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


messages_mod = _load_messages()
subjects_mod = _load_subjects()


# ---------------------------------------------------------------------------
# Load RetryOrchestrator module
# ---------------------------------------------------------------------------

def _load_orchestrator():
    mod_path = BACKEND_ROOT / "app" / "modules" / "job" / "orchestrator.py"
    spec = importlib.util.spec_from_file_location("orchestrator", mod_path)
    mod = importlib.util.module_from_spec(spec)

    settings_mock = MagicMock()
    settings_mock.max_job_retries = 3

    mocked = {
        "app.core.logging": MagicMock(get_logger=MagicMock(return_value=MagicMock())),
        "app.config": MagicMock(settings=settings_mock),
        "app.infrastructure.database.models": MagicMock(),
        "app.infrastructure.database.repositories": MagicMock(),
        "app.infrastructure.queue.messages": messages_mod,
        "app.infrastructure.queue.subjects": subjects_mod,
        "sqlalchemy": MagicMock(),
        "sqlalchemy.orm": MagicMock(),
    }
    with patch.dict("sys.modules", mocked):
        spec.loader.exec_module(mod)
    return mod


orch_mod = _load_orchestrator()
RetryOrchestrator = orch_mod.RetryOrchestrator


# ---------------------------------------------------------------------------
# Fixture: build a fresh RetryOrchestrator with mocked repos
# ---------------------------------------------------------------------------

@pytest.fixture
def orch():
    """Create RetryOrchestrator with mocked repos and queue."""
    db = MagicMock()
    queue = AsyncMock()
    o = RetryOrchestrator(db, queue)
    o.job_repo = MagicMock()
    o.file_repo = MagicMock()
    return o


@pytest.fixture
def orch_no_queue():
    """Create RetryOrchestrator without queue."""
    db = MagicMock()
    o = RetryOrchestrator(db, queue=None)
    o.job_repo = MagicMock()
    o.file_repo = MagicMock()
    return o


# ===================================================================
# decide_retry_or_dlq  (RO-001 to RO-005)
# ===================================================================

class TestDecideRetryOrDlq:
    """RO-001 to RO-005: Decide whether to retry or move to DLQ."""

    def test_ro001_retry_when_under_max_retries(self, orch):
        """RO-001: Returns 'retry' when retry_count < MAX_RETRIES and retriable."""
        job = make_job(retry_count=0, error_history="[]")
        assert orch.decide_retry_or_dlq(job, retriable=True) == "retry"

    def test_ro002_dlq_when_max_retries_exceeded(self, orch):
        """RO-002: Returns 'dlq' when retry_count >= MAX_RETRIES."""
        job = make_job(retry_count=3, error_history="[]")
        assert orch.decide_retry_or_dlq(job, retriable=True) == "dlq"

    def test_ro003_dlq_when_not_retriable(self, orch):
        """RO-003: Returns 'dlq' when retriable=False."""
        job = make_job(retry_count=0, error_history="[]")
        assert orch.decide_retry_or_dlq(job, retriable=False) == "dlq"

    def test_ro004_dlq_when_last_error_not_retriable(self, orch):
        """RO-004: Returns 'dlq' when last error in history is not retriable."""
        history = json.dumps([{"error": "fatal", "retriable": False}])
        job = make_job(retry_count=0, error_history=history)
        assert orch.decide_retry_or_dlq(job, retriable=True) == "dlq"

    def test_ro005_retry_when_error_history_malformed(self, orch):
        """RO-005: Returns 'retry' when error_history is malformed JSON (falls through)."""
        job = make_job(retry_count=0, error_history="not valid json")
        assert orch.decide_retry_or_dlq(job, retriable=True) == "retry"


# ===================================================================
# handle_failure  (RO-006 to RO-008)
# ===================================================================

class TestHandleFailure:
    """RO-006 to RO-008: Handle job failure with retry or DLQ."""

    @pytest.mark.asyncio
    async def test_ro006_calls_requeue_when_retry(self, orch):
        """RO-006: Calls requeue_job when decide returns 'retry'."""
        job = make_job(retry_count=0, error_history="[]")
        orch.requeue_job = AsyncMock()
        orch.move_to_dlq = AsyncMock()

        await orch.handle_failure(job, "timeout", retriable=True)
        orch.requeue_job.assert_awaited_once_with(job)
        orch.move_to_dlq.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ro007_calls_dlq_when_max_retries(self, orch):
        """RO-007: Calls move_to_dlq when decide returns 'dlq'."""
        job = make_job(retry_count=3, error_history="[]")
        orch.requeue_job = AsyncMock()
        orch.move_to_dlq = AsyncMock()

        await orch.handle_failure(job, "fatal error", retriable=True)
        orch.move_to_dlq.assert_awaited_once_with(job)
        orch.requeue_job.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ro008_calls_dlq_when_not_retriable(self, orch):
        """RO-008: Calls move_to_dlq when retriable=False."""
        job = make_job(retry_count=0, error_history="[]")
        orch.requeue_job = AsyncMock()
        orch.move_to_dlq = AsyncMock()

        await orch.handle_failure(job, "permanent error", retriable=False)
        orch.move_to_dlq.assert_awaited_once_with(job)
        orch.requeue_job.assert_not_awaited()


# ===================================================================
# requeue_job  (RO-009 to RO-011)
# ===================================================================

class TestRequeueJob:
    """RO-009 to RO-011: Requeue job for retry."""

    @pytest.mark.asyncio
    async def test_ro009_increments_retry_and_sets_queued(self, orch):
        """RO-009: Increments retry count and sets status to QUEUED."""
        job = make_job(job_id="job-1", method="ocr_paddle_text", tier=0, retry_count=1)
        file = make_file(file_id="file-1")
        orch.file_repo.get_active.return_value = file

        await orch.requeue_job(job)
        orch.job_repo.increment_retry.assert_called_once_with(job)
        orch.job_repo.update_status.assert_called_once_with(job, status="QUEUED")

    @pytest.mark.asyncio
    async def test_ro010_publishes_to_correct_subject(self, orch):
        """RO-010: Publishes message to correct NATS subject."""
        job = make_job(job_id="job-1", method="ocr_paddle_text", tier=0)
        file = make_file(file_id="file-1")
        orch.file_repo.get_active.return_value = file

        await orch.requeue_job(job)
        expected_subject = "ocr.ocr_paddle_text.tier0"
        orch.queue.publish.assert_awaited_once()
        call_args = orch.queue.publish.call_args
        assert call_args[0][0] == expected_subject

    @pytest.mark.asyncio
    async def test_ro011_no_publish_when_queue_unavailable(self, orch_no_queue):
        """RO-011: Sets QUEUED but does not publish when queue is None."""
        job = make_job(job_id="job-1", method="ocr_paddle_text", tier=0)
        file = make_file(file_id="file-1")
        orch_no_queue.file_repo.get_active.return_value = file

        await orch_no_queue.requeue_job(job)
        orch_no_queue.job_repo.increment_retry.assert_called_once_with(job)
        orch_no_queue.job_repo.update_status.assert_called_once_with(job, status="QUEUED")


# ===================================================================
# move_to_dlq  (RO-012 to RO-014)
# ===================================================================

class TestMoveToDlq:
    """RO-012 to RO-014: Move job to Dead Letter Queue."""

    @pytest.mark.asyncio
    async def test_ro012_sets_dead_letter_status(self, orch):
        """RO-012: Updates job status to DEAD_LETTER."""
        job = make_job(job_id="job-1", method="ocr_paddle_text", tier=0)
        file = make_file(file_id="file-1")
        orch.file_repo.get_active.return_value = file

        await orch.move_to_dlq(job)
        orch.job_repo.update_status.assert_called_once_with(job, status="DEAD_LETTER")

    @pytest.mark.asyncio
    async def test_ro013_publishes_to_dlq_subject(self, orch):
        """RO-013: Publishes to DLQ NATS subject."""
        job = make_job(job_id="job-1", method="ocr_paddle_text", tier=0)
        file = make_file(file_id="file-1")
        orch.file_repo.get_active.return_value = file

        await orch.move_to_dlq(job)
        expected_subject = "dlq.ocr_paddle_text.tier0"
        orch.queue.publish.assert_awaited_once()
        call_args = orch.queue.publish.call_args
        assert call_args[0][0] == expected_subject

    @pytest.mark.asyncio
    async def test_ro014_no_publish_when_queue_unavailable(self, orch_no_queue):
        """RO-014: Sets DEAD_LETTER but does not publish when queue is None."""
        job = make_job(job_id="job-1", method="ocr_paddle_text", tier=0)

        await orch_no_queue.move_to_dlq(job)
        orch_no_queue.job_repo.update_status.assert_called_once_with(job, status="DEAD_LETTER")


# ===================================================================
# _build_message  (RO-015)
# ===================================================================

class TestBuildMessage:
    """RO-015: Build JobMessage from job + file."""

    def test_ro015_builds_correct_message(self, orch):
        """RO-015: Builds JobMessage with all fields from job and file."""
        job = make_job(
            job_id="job-1", file_id="file-1", request_id="req-1",
            method="ocr_paddle_text", tier=0, retry_count=2,
        )
        file = make_file(file_id="file-1", object_key="u1/r1/f1/test.png")
        orch.file_repo.get_active.return_value = file

        msg = orch._build_message(job)
        assert msg.job_id == "job-1"
        assert msg.file_id == "file-1"
        assert msg.request_id == "req-1"
        assert msg.method == "ocr_paddle_text"
        assert msg.tier == 0
        assert msg.output_format == "txt"
        assert msg.object_key == "u1/r1/f1/test.png"
        assert msg.retry_count == 2
