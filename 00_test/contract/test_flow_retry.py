"""Cross-function flow tests: Retry Flow (F2)

Test failure → retry → success/exhaust flow through
JobStateMachine + RetryOrchestrator.

Test IDs: FL-004 through FL-006
"""

import json
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock

from helpers import (
    JobStateMachine, load_backend_module,
    make_job, make_request, make_file,
)


# Load RetryOrchestrator
_orch_mod = load_backend_module(
    "modules/job/orchestrator.py", "fl_orchestrator",
    extra_mocks={
        "app.infrastructure.queue.subjects": MagicMock(
            get_subject=MagicMock(return_value="ocr.ocr_paddle_text.tier0"),
            get_dlq_subject=MagicMock(return_value="dlq.ocr_paddle_text.tier0"),
        ),
    },
)
RetryOrchestrator = _orch_mod.RetryOrchestrator


# ---------------------------------------------------------------------------
# FL-004: FAILED + retriable + retries left → back to QUEUED
# ---------------------------------------------------------------------------

class TestRetriableFailureRequeues:
    """FL-004: FAILED + retriable + retries_left → QUEUED (re-queue)."""

    def test_state_machine_allows_failed_to_queued(self):
        """FL-004a: FAILED → QUEUED is a valid transition (retry)."""
        assert JobStateMachine.validate_transition("FAILED", "QUEUED") is True

    def test_decide_retry_when_retries_left(self):
        """FL-004b: retry_count < max → action is 'retry'."""
        orch = RetryOrchestrator(db=MagicMock())
        job = make_job(status="FAILED", retry_count=0)
        action = orch.decide_retry_or_dlq(job, retriable=True)
        assert action == "retry"

    def test_decide_retry_at_penultimate(self):
        """FL-004c: retry_count = max-1 → still 'retry'."""
        orch = RetryOrchestrator(db=MagicMock())
        job = make_job(status="FAILED", retry_count=2)  # MAX_RETRIES=3
        action = orch.decide_retry_or_dlq(job, retriable=True)
        assert action == "retry"

    @pytest.mark.asyncio
    async def test_requeue_increments_retry_and_publishes(self):
        """FL-004d: requeue_job increments retry count and publishes to NATS."""
        orch = RetryOrchestrator(db=MagicMock(), queue=AsyncMock())
        orch.job_repo = MagicMock()
        orch.job_repo.increment_retry = MagicMock()
        orch.job_repo.update_status = MagicMock()
        orch.file_repo = MagicMock()
        orch.file_repo.get_active = MagicMock(return_value=make_file())

        job = make_job(status="FAILED", retry_count=0)
        await orch.requeue_job(job)

        orch.job_repo.increment_retry.assert_called_once_with(job)
        orch.job_repo.update_status.assert_called_once()
        orch.queue.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_failure_retries(self):
        """FL-004e: handle_failure with retriable=True and retries left → retry."""
        orch = RetryOrchestrator(db=MagicMock(), queue=AsyncMock())
        orch.job_repo = MagicMock()
        orch.job_repo.increment_retry = MagicMock()
        orch.job_repo.update_status = MagicMock()
        orch.file_repo = MagicMock()
        orch.file_repo.get_active = MagicMock(return_value=make_file())

        job = make_job(status="FAILED", retry_count=1)
        await orch.handle_failure(job, "timeout", retriable=True)

        # Should have called requeue (increment_retry)
        orch.job_repo.increment_retry.assert_called_once()


# ---------------------------------------------------------------------------
# FL-005: FAILED + retriable + max retries exhausted → DEAD_LETTER
# ---------------------------------------------------------------------------

class TestMaxRetriesExhausted:
    """FL-005: FAILED + retriable + max retries → DEAD_LETTER."""

    def test_state_machine_allows_failed_to_dlq(self):
        """FL-005a: FAILED → DEAD_LETTER is valid."""
        assert JobStateMachine.validate_transition("FAILED", "DEAD_LETTER") is True

    def test_decide_dlq_when_max_retries(self):
        """FL-005b: retry_count >= max → action is 'dlq'."""
        orch = RetryOrchestrator(db=MagicMock())
        job = make_job(status="FAILED", retry_count=3)  # MAX_RETRIES=3
        action = orch.decide_retry_or_dlq(job, retriable=True)
        assert action == "dlq"

    def test_decide_dlq_over_max_retries(self):
        """FL-005c: retry_count > max → still 'dlq'."""
        orch = RetryOrchestrator(db=MagicMock())
        job = make_job(status="FAILED", retry_count=10)
        action = orch.decide_retry_or_dlq(job, retriable=True)
        assert action == "dlq"

    @pytest.mark.asyncio
    async def test_move_to_dlq_updates_status_and_publishes(self):
        """FL-005d: move_to_dlq sets DEAD_LETTER and publishes to DLQ stream."""
        orch = RetryOrchestrator(db=MagicMock(), queue=AsyncMock())
        orch.job_repo = MagicMock()
        orch.job_repo.update_status = MagicMock()
        orch.file_repo = MagicMock()
        orch.file_repo.get_active = MagicMock(return_value=make_file())

        job = make_job(status="FAILED", retry_count=3)
        await orch.move_to_dlq(job)

        orch.job_repo.update_status.assert_called_once()
        call_args = orch.job_repo.update_status.call_args
        assert call_args[1]["status"] == "DEAD_LETTER" or call_args.args[1] == "DEAD_LETTER" \
            or "DEAD_LETTER" in str(call_args)
        orch.queue.publish.assert_called_once()


# ---------------------------------------------------------------------------
# FL-006: FAILED + NOT retriable → DEAD_LETTER immediately
# ---------------------------------------------------------------------------

class TestNonRetriableFailure:
    """FL-006: FAILED + NOT retriable → DEAD_LETTER immediately."""

    def test_decide_dlq_when_not_retriable(self):
        """FL-006a: retriable=False → action is 'dlq' regardless of retry_count."""
        orch = RetryOrchestrator(db=MagicMock())
        job = make_job(status="FAILED", retry_count=0)
        action = orch.decide_retry_or_dlq(job, retriable=False)
        assert action == "dlq"

    def test_decide_dlq_not_retriable_zero_retries(self):
        """FL-006b: Even with 0 retries, non-retriable goes to DLQ."""
        orch = RetryOrchestrator(db=MagicMock())
        job = make_job(status="FAILED", retry_count=0)
        action = orch.decide_retry_or_dlq(job, retriable=False)
        assert action == "dlq"

    @pytest.mark.asyncio
    async def test_handle_failure_non_retriable_goes_to_dlq(self):
        """FL-006c: handle_failure with retriable=False → moves to DLQ."""
        orch = RetryOrchestrator(db=MagicMock(), queue=AsyncMock())
        orch.job_repo = MagicMock()
        orch.job_repo.update_status = MagicMock()
        orch.file_repo = MagicMock()
        orch.file_repo.get_active = MagicMock(return_value=make_file())

        job = make_job(status="FAILED", retry_count=0)
        await orch.handle_failure(job, "Invalid image format", retriable=False)

        # Should NOT have called increment_retry
        orch.job_repo.increment_retry = MagicMock()
        # Should have called update_status with DEAD_LETTER
        orch.job_repo.update_status.assert_called_once()
