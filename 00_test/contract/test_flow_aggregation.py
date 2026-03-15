"""Cross-function flow tests: Multi-job Aggregation (F5)

Test N files → N jobs → individual status updates → request status aggregation.

Test IDs: FL-013 through FL-015
"""

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock

from helpers import (
    JobStateMachine, load_backend_module,
    make_job, make_request,
)


# Load JobService
_js_mod = load_backend_module(
    "modules/job/service.py", "fl_agg_job_service",
    extra_mocks={
        "app.modules.job.state_machine": MagicMock(
            JobStateMachine=JobStateMachine,
        ),
    },
)
JobService = _js_mod.JobService


# ---------------------------------------------------------------------------
# FL-013: 3 files → 3 jobs all COMPLETED → request COMPLETED
# ---------------------------------------------------------------------------

class TestAllCompletedAggregation:
    """FL-013: 3 files → 3 jobs all COMPLETED → request COMPLETED."""

    def test_three_completed_jobs(self):
        """FL-013a: 3 COMPLETED jobs → request COMPLETED."""
        jobs = [
            make_job(job_id=f"job-{i}", status="COMPLETED")
            for i in range(3)
        ]
        assert JobStateMachine.get_request_status(jobs) == "COMPLETED"

    def test_five_completed_jobs(self):
        """FL-013b: 5 COMPLETED jobs → request COMPLETED."""
        jobs = [
            make_job(job_id=f"job-{i}", status="COMPLETED")
            for i in range(5)
        ]
        assert JobStateMachine.get_request_status(jobs) == "COMPLETED"

    @pytest.mark.asyncio
    async def test_last_job_completion_triggers_request_completed(self):
        """FL-013c: When last job completes, request status becomes COMPLETED."""
        svc = JobService(db=MagicMock())

        # 2 already completed, 1 now completing
        processing_job = make_job(job_id="job-3", status="PROCESSING")
        completed_job = make_job(job_id="job-3", status="COMPLETED")

        svc.job_repo = MagicMock()
        svc.job_repo.get_active = MagicMock(return_value=processing_job)
        svc.job_repo.update_status = MagicMock(return_value=completed_job)
        svc.job_repo.get_by_request = MagicMock(return_value=[
            make_job(job_id="job-1", status="COMPLETED"),
            make_job(job_id="job-2", status="COMPLETED"),
            completed_job,
        ])

        request = make_request(status="PROCESSING", file_count=3)
        svc.request_repo = MagicMock()
        svc.request_repo.get_active = MagicMock(return_value=request)
        svc.request_repo.increment_completed = MagicMock()
        svc.request_repo.increment_failed = MagicMock()
        svc.request_repo.update_status = MagicMock()

        result = await svc.update_job_status(
            job_id="job-3", status="COMPLETED", worker_id="w1",
        )

        assert result is not None
        svc.request_repo.update_status.assert_called_once()
        # Verify the new status is COMPLETED
        call_args = svc.request_repo.update_status.call_args
        assert call_args[0][1] == "COMPLETED"


# ---------------------------------------------------------------------------
# FL-014: 3 files → 2 COMPLETED + 1 FAILED → request PARTIAL_SUCCESS
# ---------------------------------------------------------------------------

class TestPartialSuccessAggregation:
    """FL-014: 3 files → 2 COMPLETED + 1 FAILED → request PARTIAL_SUCCESS."""

    def test_two_completed_one_failed(self):
        """FL-014a: 2 COMPLETED + 1 FAILED → PARTIAL_SUCCESS."""
        jobs = [
            make_job(job_id="job-1", status="COMPLETED"),
            make_job(job_id="job-2", status="COMPLETED"),
            make_job(job_id="job-3", status="FAILED"),
        ]
        assert JobStateMachine.get_request_status(jobs) == "PARTIAL_SUCCESS"

    def test_two_completed_one_dlq(self):
        """FL-014b: 2 COMPLETED + 1 DEAD_LETTER → PARTIAL_SUCCESS."""
        jobs = [
            make_job(job_id="job-1", status="COMPLETED"),
            make_job(job_id="job-2", status="COMPLETED"),
            make_job(job_id="job-3", status="DEAD_LETTER"),
        ]
        assert JobStateMachine.get_request_status(jobs) == "PARTIAL_SUCCESS"

    def test_one_completed_one_failed_one_cancelled(self):
        """FL-014c: Mixed terminals → PARTIAL_SUCCESS."""
        jobs = [
            make_job(status="COMPLETED"),
            make_job(status="FAILED"),
            make_job(status="CANCELLED"),
        ]
        assert JobStateMachine.get_request_status(jobs) == "PARTIAL_SUCCESS"

    @pytest.mark.asyncio
    async def test_failure_triggers_partial_success_recalculation(self):
        """FL-014d: Job failure triggers request recalculation to PARTIAL_SUCCESS."""
        svc = JobService(db=MagicMock())

        processing_job = make_job(job_id="job-3", status="PROCESSING")
        failed_job = make_job(job_id="job-3", status="FAILED")

        svc.job_repo = MagicMock()
        svc.job_repo.get_active = MagicMock(return_value=processing_job)
        svc.job_repo.update_status = MagicMock(return_value=failed_job)
        svc.job_repo.get_by_request = MagicMock(return_value=[
            make_job(job_id="job-1", status="COMPLETED"),
            make_job(job_id="job-2", status="COMPLETED"),
            failed_job,
        ])

        request = make_request(status="PROCESSING", file_count=3)
        svc.request_repo = MagicMock()
        svc.request_repo.get_active = MagicMock(return_value=request)
        svc.request_repo.increment_completed = MagicMock()
        svc.request_repo.increment_failed = MagicMock()
        svc.request_repo.update_status = MagicMock()

        result = await svc.update_job_status(
            job_id="job-3", status="FAILED", worker_id="w1",
            error="OCR timeout", retriable=True,
        )

        assert result is not None
        svc.request_repo.increment_failed.assert_called_once()
        svc.request_repo.update_status.assert_called_once()
        call_args = svc.request_repo.update_status.call_args
        assert call_args[0][1] == "PARTIAL_SUCCESS"


# ---------------------------------------------------------------------------
# FL-015: 3 files → 1 PROCESSING + 2 COMPLETED → request still PROCESSING
# ---------------------------------------------------------------------------

class TestStillProcessingAggregation:
    """FL-015: 1 PROCESSING + 2 COMPLETED → request still PROCESSING."""

    def test_one_processing_two_completed(self):
        """FL-015a: 1 PROCESSING + 2 COMPLETED → still PROCESSING."""
        jobs = [
            make_job(job_id="job-1", status="COMPLETED"),
            make_job(job_id="job-2", status="COMPLETED"),
            make_job(job_id="job-3", status="PROCESSING"),
        ]
        assert JobStateMachine.get_request_status(jobs) == "PROCESSING"

    def test_one_queued_two_completed(self):
        """FL-015b: 1 QUEUED + 2 COMPLETED → still PROCESSING."""
        jobs = [
            make_job(status="COMPLETED"),
            make_job(status="COMPLETED"),
            make_job(status="QUEUED"),
        ]
        assert JobStateMachine.get_request_status(jobs) == "PROCESSING"

    def test_empty_jobs_list(self):
        """FL-015c: Empty jobs list → PROCESSING (waiting for jobs)."""
        assert JobStateMachine.get_request_status([]) == "PROCESSING"

    def test_all_submitted(self):
        """FL-015d: All SUBMITTED → PROCESSING."""
        jobs = [make_job(status="SUBMITTED") for _ in range(3)]
        assert JobStateMachine.get_request_status(jobs) == "PROCESSING"
