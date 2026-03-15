"""Cross-function flow tests: Happy Path (F1)

Test the full job lifecycle: QUEUED → PROCESSING → COMPLETED,
with request status aggregation.

Test IDs: FL-001 through FL-003
"""

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock

from helpers import (
    JobStateMachine, JobMessage, get_subject,
    load_backend_module, make_job, make_request, make_file,
)


# Load JobService with mocked I/O
_js_mod = load_backend_module(
    "modules/job/service.py", "fl_job_service",
    extra_mocks={
        "app.modules.job.state_machine": MagicMock(
            JobStateMachine=JobStateMachine,
        ),
    },
)
JobService = _js_mod.JobService


# ---------------------------------------------------------------------------
# FL-001: Full happy path state transitions
# ---------------------------------------------------------------------------

class TestHappyPathTransitions:
    """FL-001: Submit → QUEUED → PROCESSING → COMPLETED."""

    def test_queued_to_processing_valid(self):
        """FL-001a: QUEUED → PROCESSING is valid."""
        assert JobStateMachine.validate_transition("QUEUED", "PROCESSING") is True

    def test_processing_to_completed_valid(self):
        """FL-001b: PROCESSING → COMPLETED is valid."""
        assert JobStateMachine.validate_transition("PROCESSING", "COMPLETED") is True

    def test_full_transition_chain(self):
        """FL-001c: Full chain SUBMITTED → QUEUED → PROCESSING → COMPLETED."""
        chain = ["SUBMITTED", "QUEUED", "PROCESSING", "COMPLETED"]
        for i in range(len(chain) - 1):
            assert JobStateMachine.validate_transition(chain[i], chain[i + 1]) is True, \
                f"{chain[i]} → {chain[i+1]} should be valid"

    def test_completed_is_terminal(self):
        """FL-001d: COMPLETED is a terminal state."""
        assert JobStateMachine.is_terminal("COMPLETED") is True

    @pytest.mark.asyncio
    async def test_job_service_processes_status_update(self):
        """FL-001e: JobService.update_job_status handles QUEUED→PROCESSING."""
        svc = JobService(db=MagicMock())
        job = make_job(status="QUEUED")
        request = make_request(status="PROCESSING")

        svc.job_repo = MagicMock()
        svc.job_repo.get_active = MagicMock(return_value=job)
        svc.job_repo.update_status = MagicMock(return_value=make_job(status="PROCESSING"))

        svc.request_repo = MagicMock()
        svc.request_repo.get_active = MagicMock(return_value=request)
        svc.request_repo.increment_completed = MagicMock()
        svc.request_repo.increment_failed = MagicMock()
        svc.request_repo.update_status = MagicMock()

        svc.job_repo.get_by_request = MagicMock(return_value=[
            make_job(status="PROCESSING"),
        ])

        result = await svc.update_job_status(
            job_id="job-1", status="PROCESSING", worker_id="w1",
        )
        assert result is not None
        svc.job_repo.update_status.assert_called_once()


# ---------------------------------------------------------------------------
# FL-002: Completion triggers request status recalculation
# ---------------------------------------------------------------------------

class TestCompletionAggregation:
    """FL-002: COMPLETED triggers request status recalculation."""

    @pytest.mark.asyncio
    async def test_single_job_completed_updates_request(self):
        """FL-002a: Single job COMPLETED → request becomes COMPLETED."""
        svc = JobService(db=MagicMock())
        job = make_job(status="PROCESSING")
        request = make_request(status="PROCESSING")

        completed_job = make_job(status="COMPLETED")
        svc.job_repo = MagicMock()
        svc.job_repo.get_active = MagicMock(return_value=job)
        svc.job_repo.update_status = MagicMock(return_value=completed_job)
        svc.job_repo.get_by_request = MagicMock(return_value=[completed_job])

        svc.request_repo = MagicMock()
        svc.request_repo.get_active = MagicMock(return_value=request)
        svc.request_repo.increment_completed = MagicMock()
        svc.request_repo.increment_failed = MagicMock()
        svc.request_repo.update_status = MagicMock()

        result = await svc.update_job_status(
            job_id="job-1", status="COMPLETED", worker_id="w1",
        )

        assert result is not None
        # Verify request status recalculation happened
        svc.request_repo.increment_completed.assert_called_once()
        svc.request_repo.update_status.assert_called_once()

    def test_aggregation_all_completed(self):
        """FL-002b: All jobs COMPLETED → request COMPLETED."""
        jobs = [make_job(status="COMPLETED") for _ in range(3)]
        assert JobStateMachine.get_request_status(jobs) == "COMPLETED"


# ---------------------------------------------------------------------------
# FL-003: Result file available after COMPLETED
# ---------------------------------------------------------------------------

class TestResultAvailability:
    """FL-003: Result file available after COMPLETED status."""

    @pytest.mark.asyncio
    async def test_completed_job_with_result_path(self):
        """FL-003a: Completed job has result_path → get_job_result returns data."""
        from unittest.mock import patch

        svc = JobService(db=MagicMock())

        job_with_result = make_job(
            status="COMPLETED",
            result_path="results/job-1/output.txt",
        )

        svc.job_repo = MagicMock()
        svc.job_repo.get_active = MagicMock(return_value=job_with_result)

        svc.request_repo = MagicMock()
        svc.request_repo.get_active = MagicMock(
            return_value=make_request(user_id="user-1"),
        )

        storage = AsyncMock()
        storage.download = AsyncMock(return_value=b"OCR result text")

        # Mock settings.minio_bucket_results used by get_job_result
        mock_settings = MagicMock()
        mock_settings.minio_bucket_results = "test-results-bucket"
        with patch.dict("sys.modules", {"app.config": MagicMock(settings=mock_settings)}):
            result = await svc.get_job_result("job-1", "user-1", storage)
        assert result is not None
        job_obj, content = result
        assert content == b"OCR result text"
        assert job_obj.result_path == "results/job-1/output.txt"

    @pytest.mark.asyncio
    async def test_non_completed_job_no_result(self):
        """FL-003b: Non-completed job → get_job_result returns None."""
        svc = JobService(db=MagicMock())

        job = make_job(status="PROCESSING", result_path=None)
        svc.job_repo = MagicMock()
        svc.job_repo.get_active = MagicMock(return_value=job)

        svc.request_repo = MagicMock()
        svc.request_repo.get_active = MagicMock(
            return_value=make_request(user_id="user-1"),
        )

        result = await svc.get_job_result("job-1", "user-1", AsyncMock())
        assert result is None
