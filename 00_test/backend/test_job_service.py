"""
Test cases for M2: JobService Refactor

Covers:
- update_job_status triggers request status recalculation
- cancel_request only cancels QUEUED jobs
- Ownership verification
- State transition validation
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from types import SimpleNamespace
from pathlib import Path
import importlib.util
import sys


# Load state_machine directly
state_machine_path = Path(__file__).parent.parent.parent / "02_backend" / "app" / "modules" / "job" / "state_machine.py"
spec_sm = importlib.util.spec_from_file_location("state_machine", state_machine_path)
state_machine_mod = importlib.util.module_from_spec(spec_sm)
spec_sm.loader.exec_module(state_machine_mod)
JobStateMachine = state_machine_mod.JobStateMachine


# Load JobService with mocked deps
@pytest.fixture
def job_service_class():
    logger_mock = MagicMock()
    settings_mock = MagicMock()
    settings_mock.minio_bucket_results = "results"

    mocked_modules = {
        "app.core.logging": MagicMock(get_logger=MagicMock(return_value=logger_mock)),
        "app.config": MagicMock(settings=settings_mock),
        "app.infrastructure.database.models": MagicMock(),
        "app.infrastructure.database.repositories": MagicMock(),
        "app.modules.job.state_machine": state_machine_mod,
    }
    with patch.dict("sys.modules", mocked_modules):
        svc_path = Path(__file__).parent.parent.parent / "02_backend" / "app" / "modules" / "job" / "service.py"
        spec = importlib.util.spec_from_file_location("job_service", svc_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        yield mod.JobService


def make_request(request_id="req-1", user_id="user-1", status="PROCESSING", total_files=3):
    return SimpleNamespace(
        id=request_id, user_id=user_id, status=status, total_files=total_files,
        completed_files=0, failed_files=0,
    )


def make_job(job_id="job-1", request_id="req-1", status="PROCESSING", retry_count=0):
    return SimpleNamespace(
        id=job_id, request_id=request_id, status=status, retry_count=retry_count,
        error_history="[]", result_path=None, method="ocr_text_raw", tier=0,
    )


class TestGetRequest:
    @pytest.mark.asyncio
    async def test_get_request_returns_owned(self, job_service_class):
        svc = job_service_class(db=MagicMock())
        req = make_request(user_id="user-1")
        svc.request_repo.get_active = MagicMock(return_value=req)

        result = await svc.get_request("req-1", "user-1")
        assert result is not None
        assert result.id == "req-1"

    @pytest.mark.asyncio
    async def test_get_request_returns_none_for_wrong_owner(self, job_service_class):
        svc = job_service_class(db=MagicMock())
        req = make_request(user_id="user-1")
        svc.request_repo.get_active = MagicMock(return_value=req)

        result = await svc.get_request("req-1", "user-2")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_request_returns_none_for_missing(self, job_service_class):
        svc = job_service_class(db=MagicMock())
        svc.request_repo.get_active = MagicMock(return_value=None)

        result = await svc.get_request("req-404", "user-1")
        assert result is None


class TestGetRequestWithJobs:
    @pytest.mark.asyncio
    async def test_returns_request_and_jobs(self, job_service_class):
        svc = job_service_class(db=MagicMock())
        req = make_request()
        jobs = [make_job("j1"), make_job("j2")]
        svc.request_repo.get_active = MagicMock(return_value=req)
        svc.job_repo.get_by_request = MagicMock(return_value=jobs)

        result = await svc.get_request_with_jobs("req-1", "user-1")
        assert result is not None
        request, job_list = result
        assert request.id == "req-1"
        assert len(job_list) == 2


class TestGetJob:
    @pytest.mark.asyncio
    async def test_get_job_verifies_ownership(self, job_service_class):
        svc = job_service_class(db=MagicMock())
        job = make_job()
        req = make_request(user_id="user-1")
        svc.job_repo.get_active = MagicMock(return_value=job)
        svc.request_repo.get_active = MagicMock(return_value=req)

        # Correct owner
        result = await svc.get_job("job-1", "user-1")
        assert result is not None

        # Wrong owner
        result = await svc.get_job("job-1", "user-2")
        assert result is None


class TestCancelRequest:
    @pytest.mark.asyncio
    async def test_cancel_request_only_queued(self, job_service_class):
        svc = job_service_class(db=MagicMock())
        req = make_request()
        svc.request_repo.get_active = MagicMock(return_value=req)
        svc.job_repo.get_queued_by_request = MagicMock(return_value=[make_job(status="QUEUED")])
        svc.job_repo.cancel_jobs = MagicMock(return_value=1)
        svc.job_repo.get_by_request = MagicMock(return_value=[make_job(status="CANCELLED")])
        svc.request_repo.update_status = MagicMock()

        result = await svc.cancel_request("req-1", "user-1")
        assert result["success"] is True
        assert result["cancelled_jobs"] == 1

    @pytest.mark.asyncio
    async def test_cancel_request_not_found(self, job_service_class):
        svc = job_service_class(db=MagicMock())
        svc.request_repo.get_active = MagicMock(return_value=None)

        result = await svc.cancel_request("req-404", "user-1")
        assert result["success"] is False


class TestCancelJob:
    @pytest.mark.asyncio
    async def test_cancel_queued_job(self, job_service_class):
        svc = job_service_class(db=MagicMock())
        job = make_job(status="QUEUED")
        req = make_request()
        svc.job_repo.get_active = MagicMock(return_value=job)
        svc.request_repo.get_active = MagicMock(return_value=req)
        svc.job_repo.cancel_jobs = MagicMock(return_value=1)
        svc.job_repo.get_by_request = MagicMock(return_value=[make_job(status="CANCELLED")])
        svc.request_repo.update_status = MagicMock()

        result = await svc.cancel_job("job-1", "user-1")
        assert result["success"] is True
        assert result["cancelled"] is True

    @pytest.mark.asyncio
    async def test_cancel_non_queued_job_fails(self, job_service_class):
        svc = job_service_class(db=MagicMock())
        job = make_job(status="PROCESSING")
        req = make_request()
        svc.job_repo.get_active = MagicMock(return_value=job)
        svc.request_repo.get_active = MagicMock(return_value=req)

        result = await svc.cancel_job("job-1", "user-1")
        assert result["success"] is False
        assert "PROCESSING" in result["message"]


class TestUpdateJobStatus:
    @pytest.mark.asyncio
    async def test_completed_triggers_request_recalculation(self, job_service_class):
        svc = job_service_class(db=MagicMock())
        job = make_job(status="PROCESSING")
        updated_job = make_job(status="COMPLETED")
        req = make_request()

        svc.job_repo.get_active = MagicMock(return_value=job)
        svc.job_repo.update_status = MagicMock(return_value=updated_job)
        svc.request_repo.get_active = MagicMock(return_value=req)
        svc.request_repo.increment_completed = MagicMock()
        svc.job_repo.get_by_request = MagicMock(return_value=[
            make_job(status="COMPLETED"), make_job(status="COMPLETED"), make_job(status="COMPLETED")
        ])
        svc.request_repo.update_status = MagicMock()

        result = await svc.update_job_status("job-1", "COMPLETED", "worker-1")
        assert result is not None
        assert result.status == "COMPLETED"
        svc.request_repo.increment_completed.assert_called_once()
        svc.request_repo.update_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_failed_triggers_increment_failed(self, job_service_class):
        svc = job_service_class(db=MagicMock())
        job = make_job(status="PROCESSING")
        updated_job = make_job(status="FAILED")
        req = make_request()

        svc.job_repo.get_active = MagicMock(return_value=job)
        svc.job_repo.update_status = MagicMock(return_value=updated_job)
        svc.request_repo.get_active = MagicMock(return_value=req)
        svc.request_repo.increment_failed = MagicMock()
        svc.job_repo.get_by_request = MagicMock(return_value=[make_job(status="FAILED")])
        svc.request_repo.update_status = MagicMock()

        result = await svc.update_job_status("job-1", "FAILED", "worker-1", error="timeout")
        assert result is not None
        svc.request_repo.increment_failed.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_transition_returns_none(self, job_service_class):
        svc = job_service_class(db=MagicMock())
        job = make_job(status="COMPLETED")  # terminal state
        svc.job_repo.get_active = MagicMock(return_value=job)

        result = await svc.update_job_status("job-1", "PROCESSING", "worker-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_job_returns_none(self, job_service_class):
        svc = job_service_class(db=MagicMock())
        svc.job_repo.get_active = MagicMock(return_value=None)

        result = await svc.update_job_status("job-404", "COMPLETED", "worker-1")
        assert result is None
