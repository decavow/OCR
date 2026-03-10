"""
Test cases for M6: Request Status Auto-Update (Integration)

Verifies that request status is correctly recalculated when job statuses change.
Tests the full flow through JobService.update_job_status() -> _recalculate_request_status().

Scenarios:
- All completed -> COMPLETED
- Mix completed + failed -> PARTIAL_SUCCESS
- All failed -> FAILED
- Partial completion (still processing) -> PROCESSING
- Cancel + complete -> PARTIAL_SUCCESS
"""

import pytest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from pathlib import Path
import importlib.util


# Load state_machine
state_machine_path = Path(__file__).parent.parent.parent / "02_backend" / "app" / "modules" / "job" / "state_machine.py"
spec_sm = importlib.util.spec_from_file_location("state_machine", state_machine_path)
state_machine_mod = importlib.util.module_from_spec(spec_sm)
spec_sm.loader.exec_module(state_machine_mod)


@pytest.fixture
def job_service_class():
    logger_mock = MagicMock()
    settings_mock = MagicMock()
    settings_mock.max_job_retries = 3

    mocked_modules = {
        "app.core.logging": MagicMock(get_logger=MagicMock(return_value=logger_mock)),
        "app.config": MagicMock(settings=settings_mock),
        "app.infrastructure.database.models": MagicMock(),
        "app.infrastructure.database.repositories": MagicMock(),
        "app.modules.job.state_machine": state_machine_mod,
    }
    with patch.dict("sys.modules", mocked_modules):
        svc_path = Path(__file__).parent.parent.parent / "02_backend" / "app" / "modules" / "job" / "service.py"
        spec = importlib.util.spec_from_file_location("job_service_int", svc_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        yield mod.JobService


def make_request(request_id="req-1", status="PROCESSING", total_files=3):
    return SimpleNamespace(
        id=request_id, user_id="user-1", status=status,
        total_files=total_files, completed_files=0, failed_files=0,
    )


def make_job(job_id, status, request_id="req-1"):
    return SimpleNamespace(
        id=job_id, request_id=request_id, status=status,
        retry_count=0, error_history="[]", file_id=f"file-{job_id}",
        method="ocr_text_raw", tier=0, max_retries=3,
    )


class TestRequestStatusIntegration:
    """End-to-end scenarios for request status recalculation."""

    @pytest.mark.asyncio
    async def test_all_3_completed_request_becomes_completed(self, job_service_class):
        """Complete all 3 jobs -> request should become COMPLETED."""
        svc = job_service_class(db=MagicMock())
        req = make_request(total_files=3)

        # Track status updates
        status_updates = []
        original_update = svc.request_repo.update_status

        def track_update(request, new_status):
            status_updates.append(new_status)
            request.status = new_status

        svc.request_repo.update_status = MagicMock(side_effect=track_update)
        svc.request_repo.get_active = MagicMock(return_value=req)
        svc.request_repo.increment_completed = MagicMock()

        # Simulate completing jobs one by one
        for i, job_id in enumerate(["j1", "j2", "j3"]):
            # This job is PROCESSING -> will be COMPLETED
            processing_job = make_job(job_id, "PROCESSING")
            completed_job = make_job(job_id, "COMPLETED")

            svc.job_repo.get_active = MagicMock(return_value=processing_job)
            svc.job_repo.update_status = MagicMock(return_value=completed_job)

            # After this update, all jobs up to this point are COMPLETED, rest PROCESSING
            completed_so_far = [make_job(f"j{x+1}", "COMPLETED") for x in range(i + 1)]
            remaining = [make_job(f"j{x+1}", "PROCESSING") for x in range(i + 1, 3)]
            svc.job_repo.get_by_request = MagicMock(return_value=completed_so_far + remaining)

            await svc.update_job_status(job_id, "COMPLETED", "worker-1")

        # Last update should set request to COMPLETED
        assert "COMPLETED" in status_updates

    @pytest.mark.asyncio
    async def test_2_completed_1_failed_becomes_partial_success(self, job_service_class):
        """2 completed + 1 failed -> PARTIAL_SUCCESS."""
        svc = job_service_class(db=MagicMock())
        req = make_request(total_files=3)

        final_status = []
        def track_update(request, new_status):
            final_status.append(new_status)
            request.status = new_status

        svc.request_repo.update_status = MagicMock(side_effect=track_update)
        svc.request_repo.get_active = MagicMock(return_value=req)
        svc.request_repo.increment_completed = MagicMock()
        svc.request_repo.increment_failed = MagicMock()

        # Final state: 2 COMPLETED + 1 FAILED
        final_jobs = [
            make_job("j1", "COMPLETED"),
            make_job("j2", "COMPLETED"),
            make_job("j3", "FAILED"),
        ]

        # Last job fails
        processing_job = make_job("j3", "PROCESSING")
        failed_job = make_job("j3", "FAILED")
        svc.job_repo.get_active = MagicMock(return_value=processing_job)
        svc.job_repo.update_status = MagicMock(return_value=failed_job)
        svc.job_repo.get_by_request = MagicMock(return_value=final_jobs)

        await svc.update_job_status("j3", "FAILED", "worker-1", error="timeout")

        assert "PARTIAL_SUCCESS" in final_status

    @pytest.mark.asyncio
    async def test_all_failed_becomes_failed(self, job_service_class):
        """All 3 jobs failed -> FAILED."""
        svc = job_service_class(db=MagicMock())
        req = make_request(total_files=3)

        final_status = []
        def track_update(request, new_status):
            final_status.append(new_status)
            request.status = new_status

        svc.request_repo.update_status = MagicMock(side_effect=track_update)
        svc.request_repo.get_active = MagicMock(return_value=req)
        svc.request_repo.increment_failed = MagicMock()

        all_failed = [make_job(f"j{i}", "FAILED") for i in range(1, 4)]

        processing_job = make_job("j3", "PROCESSING")
        failed_job = make_job("j3", "FAILED")
        svc.job_repo.get_active = MagicMock(return_value=processing_job)
        svc.job_repo.update_status = MagicMock(return_value=failed_job)
        svc.job_repo.get_by_request = MagicMock(return_value=all_failed)

        await svc.update_job_status("j3", "FAILED", "worker-1", error="crash")

        assert "FAILED" in final_status

    @pytest.mark.asyncio
    async def test_1_processing_keeps_request_processing(self, job_service_class):
        """2 completed + 1 still processing -> request stays PROCESSING."""
        svc = job_service_class(db=MagicMock())
        req = make_request(total_files=3, status="PROCESSING")

        svc.request_repo.update_status = MagicMock()
        svc.request_repo.get_active = MagicMock(return_value=req)
        svc.request_repo.increment_completed = MagicMock()

        mixed_jobs = [
            make_job("j1", "COMPLETED"),
            make_job("j2", "COMPLETED"),
            make_job("j3", "PROCESSING"),  # still going
        ]

        processing_job = make_job("j2", "PROCESSING")
        completed_job = make_job("j2", "COMPLETED")
        svc.job_repo.get_active = MagicMock(return_value=processing_job)
        svc.job_repo.update_status = MagicMock(return_value=completed_job)
        svc.job_repo.get_by_request = MagicMock(return_value=mixed_jobs)

        await svc.update_job_status("j2", "COMPLETED", "worker-1")

        # Status should NOT change (stays PROCESSING)
        svc.request_repo.update_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_cancel_plus_complete_becomes_partial_success(self, job_service_class):
        """1 cancelled + 2 completed -> PARTIAL_SUCCESS."""
        svc = job_service_class(db=MagicMock())
        req = make_request(total_files=3)

        final_status = []
        def track_update(request, new_status):
            final_status.append(new_status)
            request.status = new_status

        svc.request_repo.update_status = MagicMock(side_effect=track_update)
        svc.request_repo.get_active = MagicMock(return_value=req)
        svc.request_repo.increment_completed = MagicMock()

        mixed_jobs = [
            make_job("j1", "CANCELLED"),
            make_job("j2", "COMPLETED"),
            make_job("j3", "COMPLETED"),
        ]

        processing_job = make_job("j3", "PROCESSING")
        completed_job = make_job("j3", "COMPLETED")
        svc.job_repo.get_active = MagicMock(return_value=processing_job)
        svc.job_repo.update_status = MagicMock(return_value=completed_job)
        svc.job_repo.get_by_request = MagicMock(return_value=mixed_jobs)

        await svc.update_job_status("j3", "COMPLETED", "worker-1")

        assert "PARTIAL_SUCCESS" in final_status
