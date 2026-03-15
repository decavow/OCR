"""Unit tests for JobService (02_backend/app/modules/job/service.py).

Service-layer tests with mocked repositories and external dependencies.

Test IDs: JS-001 to JS-026
"""

import importlib.util
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

# Import helpers from conftest (plain functions, not fixtures)
sys.path.insert(0, str(TEST_DIR))
from conftest import make_job, make_request, make_file
sys.path.pop(0)


# ---------------------------------------------------------------------------
# Load state_machine (real module, no app dependencies)
# ---------------------------------------------------------------------------

def _load_state_machine():
    mod_path = BACKEND_ROOT / "app" / "modules" / "job" / "state_machine.py"
    spec = importlib.util.spec_from_file_location("state_machine", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sm_module = _load_state_machine()


# ---------------------------------------------------------------------------
# Load JobService module with mocked dependencies
# ---------------------------------------------------------------------------

def _load_job_service():
    mod_path = BACKEND_ROOT / "app" / "modules" / "job" / "service.py"
    spec = importlib.util.spec_from_file_location("job_service", mod_path)
    mod = importlib.util.module_from_spec(spec)

    mocked = {
        "app.core.logging": MagicMock(get_logger=MagicMock(return_value=MagicMock())),
        "app.config": MagicMock(settings=MagicMock()),
        "app.infrastructure.database.models": MagicMock(),
        "app.infrastructure.database.repositories": MagicMock(),
        "app.modules.job.state_machine": sm_module,
        "sqlalchemy": MagicMock(),
        "sqlalchemy.orm": MagicMock(),
    }
    with patch.dict("sys.modules", mocked):
        spec.loader.exec_module(mod)
    return mod


job_service_mod = _load_job_service()
JobService = job_service_mod.JobService


# ---------------------------------------------------------------------------
# Fixture: build a fresh JobService with mocked repos
# ---------------------------------------------------------------------------

@pytest.fixture
def svc():
    """Create JobService with all repos replaced by mocks."""
    db = MagicMock()
    service = JobService(db)
    service.job_repo = MagicMock()
    service.request_repo = MagicMock()
    service.file_repo = MagicMock()
    # state_machine is the real one, keep it
    return service


# ===================================================================
# get_request  (JS-001 to JS-003)
# ===================================================================

class TestGetRequest:
    """JS-001 to JS-003: Retrieve request with ownership check."""

    @pytest.mark.asyncio
    async def test_js001_returns_request_when_found_and_owned(self, svc):
        """JS-001: Returns request when found and user_id matches."""
        req = make_request(request_id="req-1", user_id="user-1")
        svc.request_repo.get_active.return_value = req

        result = await svc.get_request("req-1", "user-1")
        assert result is req
        svc.request_repo.get_active.assert_called_once_with("req-1")

    @pytest.mark.asyncio
    async def test_js002_returns_none_when_not_found(self, svc):
        """JS-002: Returns None when request not found."""
        svc.request_repo.get_active.return_value = None

        result = await svc.get_request("req-999", "user-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_js003_returns_none_when_wrong_user(self, svc):
        """JS-003: Returns None when user_id does not match."""
        req = make_request(request_id="req-1", user_id="user-1")
        svc.request_repo.get_active.return_value = req

        result = await svc.get_request("req-1", "user-other")
        assert result is None


# ===================================================================
# get_request_with_jobs  (JS-004 to JS-005)
# ===================================================================

class TestGetRequestWithJobs:
    """JS-004 to JS-005: Get request with associated jobs."""

    @pytest.mark.asyncio
    async def test_js004_returns_tuple_when_found(self, svc):
        """JS-004: Returns (request, jobs) tuple when found and owned."""
        req = make_request(request_id="req-1", user_id="user-1")
        jobs = [make_job(job_id="job-1"), make_job(job_id="job-2")]
        svc.request_repo.get_active.return_value = req
        svc.job_repo.get_by_request.return_value = jobs

        result = await svc.get_request_with_jobs("req-1", "user-1")
        assert result is not None
        assert result[0] is req
        assert result[1] is jobs

    @pytest.mark.asyncio
    async def test_js005_returns_none_when_not_found(self, svc):
        """JS-005: Returns None when request not found."""
        svc.request_repo.get_active.return_value = None

        result = await svc.get_request_with_jobs("req-999", "user-1")
        assert result is None


# ===================================================================
# get_job  (JS-006 to JS-008)
# ===================================================================

class TestGetJob:
    """JS-006 to JS-008: Get job with ownership verification via request."""

    @pytest.mark.asyncio
    async def test_js006_returns_job_when_found_and_owned(self, svc):
        """JS-006: Returns job when found and ownership verified."""
        job = make_job(job_id="job-1", request_id="req-1")
        req = make_request(request_id="req-1", user_id="user-1")
        svc.job_repo.get_active.return_value = job
        svc.request_repo.get_active.return_value = req

        result = await svc.get_job("job-1", "user-1")
        assert result is job

    @pytest.mark.asyncio
    async def test_js007_returns_none_when_job_not_found(self, svc):
        """JS-007: Returns None when job not found."""
        svc.job_repo.get_active.return_value = None

        result = await svc.get_job("job-999", "user-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_js008_returns_none_when_wrong_owner(self, svc):
        """JS-008: Returns None when request owner doesn't match."""
        job = make_job(job_id="job-1", request_id="req-1")
        req = make_request(request_id="req-1", user_id="user-other")
        svc.job_repo.get_active.return_value = job
        svc.request_repo.get_active.return_value = req

        result = await svc.get_job("job-1", "user-1")
        assert result is None


# ===================================================================
# get_job_result  (JS-009 to JS-011)
# ===================================================================

class TestGetJobResult:
    """JS-009 to JS-011: Get job result content."""

    @pytest.mark.asyncio
    async def test_js009_returns_job_and_content_when_completed(self, svc):
        """JS-009: Returns (job, content) when job COMPLETED with result_path."""
        job = make_job(job_id="job-1", status="COMPLETED", result_path="results/r1.txt")
        req = make_request(request_id="req-1", user_id="user-1")
        svc.job_repo.get_active.return_value = job
        svc.request_repo.get_active.return_value = req

        storage = MagicMock()
        storage.download = AsyncMock(return_value=b"OCR result content")

        # get_job_result does a runtime `from app.config import settings`
        settings_mock = MagicMock()
        settings_mock.minio_bucket_results = "results"
        with patch.dict("sys.modules", {"app.config": MagicMock(settings=settings_mock)}):
            result = await svc.get_job_result("job-1", "user-1", storage)
        assert result is not None
        assert result[0] is job
        assert result[1] == b"OCR result content"

    @pytest.mark.asyncio
    async def test_js010_returns_none_when_not_completed(self, svc):
        """JS-010: Returns None when job is not in COMPLETED status."""
        job = make_job(job_id="job-1", status="PROCESSING", result_path=None)
        req = make_request(request_id="req-1", user_id="user-1")
        svc.job_repo.get_active.return_value = job
        svc.request_repo.get_active.return_value = req

        storage = MagicMock()
        result = await svc.get_job_result("job-1", "user-1", storage)
        assert result is None

    @pytest.mark.asyncio
    async def test_js011_returns_none_when_no_result_path(self, svc):
        """JS-011: Returns None when job is COMPLETED but result_path is None."""
        job = make_job(job_id="job-1", status="COMPLETED", result_path=None)
        req = make_request(request_id="req-1", user_id="user-1")
        svc.job_repo.get_active.return_value = job
        svc.request_repo.get_active.return_value = req

        storage = MagicMock()
        result = await svc.get_job_result("job-1", "user-1", storage)
        assert result is None


# ===================================================================
# cancel_request  (JS-012 to JS-015)
# ===================================================================

class TestCancelRequest:
    """JS-012 to JS-015: Cancel all QUEUED jobs in a request."""

    @pytest.mark.asyncio
    async def test_js012_cancels_queued_jobs(self, svc):
        """JS-012: Cancels queued jobs and returns success."""
        req = make_request(request_id="req-1", user_id="user-1")
        queued = [make_job(job_id="j1", status="QUEUED"), make_job(job_id="j2", status="QUEUED")]
        svc.request_repo.get_active.return_value = req
        svc.job_repo.get_queued_by_request.return_value = queued
        svc.job_repo.cancel_jobs.return_value = 2
        svc.job_repo.get_by_request.return_value = []  # for recalculate

        result = await svc.cancel_request("req-1", "user-1")
        assert result["success"] is True
        assert result["cancelled_jobs"] == 2

    @pytest.mark.asyncio
    async def test_js013_returns_failure_when_not_found(self, svc):
        """JS-013: Returns failure when request not found."""
        svc.request_repo.get_active.return_value = None

        result = await svc.cancel_request("req-999", "user-1")
        assert result["success"] is False
        assert result["cancelled_jobs"] == 0

    @pytest.mark.asyncio
    async def test_js014_returns_zero_when_no_queued(self, svc):
        """JS-014: Returns success with 0 cancelled when no QUEUED jobs."""
        req = make_request(request_id="req-1", user_id="user-1")
        svc.request_repo.get_active.return_value = req
        svc.job_repo.get_queued_by_request.return_value = []
        svc.job_repo.cancel_jobs.return_value = 0
        svc.job_repo.get_by_request.return_value = []

        result = await svc.cancel_request("req-1", "user-1")
        assert result["success"] is True
        assert result["cancelled_jobs"] == 0

    @pytest.mark.asyncio
    async def test_js015_recalculates_request_status(self, svc):
        """JS-015: Recalculates request status after cancellation."""
        req = make_request(request_id="req-1", user_id="user-1", status="PROCESSING")
        jobs_after = [make_job(status="CANCELLED"), make_job(status="COMPLETED")]
        svc.request_repo.get_active.return_value = req
        svc.job_repo.get_queued_by_request.return_value = []
        svc.job_repo.cancel_jobs.return_value = 0
        svc.job_repo.get_by_request.return_value = jobs_after

        await svc.cancel_request("req-1", "user-1")
        # The state_machine should compute PARTIAL_SUCCESS for mix of CANCELLED + COMPLETED
        svc.request_repo.update_status.assert_called_once_with(req, "PARTIAL_SUCCESS")


# ===================================================================
# cancel_job  (JS-016 to JS-018)
# ===================================================================

class TestCancelJob:
    """JS-016 to JS-018: Cancel single QUEUED job."""

    @pytest.mark.asyncio
    async def test_js016_cancels_queued_job(self, svc):
        """JS-016: Cancels a QUEUED job successfully."""
        job = make_job(job_id="job-1", status="QUEUED", request_id="req-1")
        req = make_request(request_id="req-1", user_id="user-1")
        svc.job_repo.get_active.return_value = job
        svc.request_repo.get_active.return_value = req
        svc.job_repo.cancel_jobs.return_value = 1
        svc.job_repo.get_by_request.return_value = []

        result = await svc.cancel_job("job-1", "user-1")
        assert result["success"] is True
        assert result["cancelled"] is True

    @pytest.mark.asyncio
    async def test_js017_fails_for_non_queued_job(self, svc):
        """JS-017: Cannot cancel job that is not QUEUED."""
        job = make_job(job_id="job-1", status="PROCESSING", request_id="req-1")
        req = make_request(request_id="req-1", user_id="user-1")
        svc.job_repo.get_active.return_value = job
        svc.request_repo.get_active.return_value = req

        result = await svc.cancel_job("job-1", "user-1")
        assert result["success"] is False
        assert result["cancelled"] is False
        assert "PROCESSING" in result["message"]

    @pytest.mark.asyncio
    async def test_js018_fails_when_job_not_found(self, svc):
        """JS-018: Returns failure when job not found."""
        svc.job_repo.get_active.return_value = None

        result = await svc.cancel_job("job-999", "user-1")
        assert result["success"] is False
        assert result["cancelled"] is False


# ===================================================================
# update_job_status  (JS-019 to JS-024)
# ===================================================================

class TestUpdateJobStatus:
    """JS-019 to JS-024: Update job status and trigger side effects."""

    @pytest.mark.asyncio
    async def test_js019_updates_status_successfully(self, svc):
        """JS-019: Updates job status via repo when transition is valid."""
        job = make_job(job_id="job-1", status="PROCESSING")
        updated_job = make_job(job_id="job-1", status="COMPLETED")
        req = make_request(request_id="req-1", user_id="user-1")
        svc.job_repo.get_active.return_value = job
        svc.job_repo.update_status.return_value = updated_job
        svc.request_repo.get_active.return_value = req
        svc.job_repo.get_by_request.return_value = [updated_job]

        result = await svc.update_job_status("job-1", "COMPLETED", "worker-1")
        assert result is updated_job
        svc.job_repo.update_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_js020_returns_none_when_job_not_found(self, svc):
        """JS-020: Returns None when job not found."""
        svc.job_repo.get_active.return_value = None

        result = await svc.update_job_status("job-999", "COMPLETED", "worker-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_js021_returns_none_for_invalid_transition(self, svc):
        """JS-021: Returns None when state transition is invalid."""
        job = make_job(job_id="job-1", status="COMPLETED")
        svc.job_repo.get_active.return_value = job

        result = await svc.update_job_status("job-1", "PROCESSING", "worker-1")
        assert result is None
        svc.job_repo.update_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_js022_increments_completed_counter(self, svc):
        """JS-022: Increments request completed counter on COMPLETED."""
        job = make_job(job_id="job-1", status="PROCESSING")
        updated_job = make_job(job_id="job-1", status="COMPLETED")
        req = make_request(request_id="req-1", user_id="user-1")
        svc.job_repo.get_active.return_value = job
        svc.job_repo.update_status.return_value = updated_job
        svc.request_repo.get_active.return_value = req
        svc.job_repo.get_by_request.return_value = [updated_job]

        await svc.update_job_status("job-1", "COMPLETED", "worker-1")
        svc.request_repo.increment_completed.assert_called_once_with(req)

    @pytest.mark.asyncio
    async def test_js023_increments_failed_counter(self, svc):
        """JS-023: Increments request failed counter on FAILED."""
        job = make_job(job_id="job-1", status="PROCESSING")
        updated_job = make_job(job_id="job-1", status="FAILED")
        req = make_request(request_id="req-1", user_id="user-1")
        svc.job_repo.get_active.return_value = job
        svc.job_repo.update_status.return_value = updated_job
        svc.request_repo.get_active.return_value = req
        svc.job_repo.get_by_request.return_value = [updated_job]

        # Patch _handle_retry to avoid orchestrator import side effects
        svc._handle_retry = AsyncMock()

        await svc.update_job_status("job-1", "FAILED", "worker-1", error="timeout")
        svc.request_repo.increment_failed.assert_called_once_with(req)

    @pytest.mark.asyncio
    async def test_js024_triggers_retry_on_failed_retriable(self, svc):
        """JS-024: Triggers _handle_retry when FAILED + retriable=True."""
        job = make_job(job_id="job-1", status="PROCESSING")
        updated_job = make_job(job_id="job-1", status="FAILED")
        req = make_request(request_id="req-1", user_id="user-1")
        svc.job_repo.get_active.return_value = job
        svc.job_repo.update_status.return_value = updated_job
        svc.request_repo.get_active.return_value = req
        svc.job_repo.get_by_request.return_value = [updated_job]

        svc._handle_retry = AsyncMock()

        await svc.update_job_status(
            "job-1", "FAILED", "worker-1", error="OOM", retriable=True,
        )
        svc._handle_retry.assert_awaited_once_with(updated_job, "OOM", True)


# ===================================================================
# _recalculate_request_status  (JS-025 to JS-026)
# ===================================================================

class TestRecalculateRequestStatus:
    """JS-025 to JS-026: Recalculate request status from jobs."""

    def test_js025_updates_status_when_changed(self, svc):
        """JS-025: Updates request status when recalculated status differs."""
        req = make_request(request_id="req-1", status="PROCESSING")
        jobs = [
            SimpleNamespace(status="COMPLETED"),
            SimpleNamespace(status="COMPLETED"),
        ]
        svc.job_repo.get_by_request.return_value = jobs

        svc._recalculate_request_status(req)
        svc.request_repo.update_status.assert_called_once_with(req, "COMPLETED")

    def test_js026_no_update_when_status_unchanged(self, svc):
        """JS-026: Does not update when recalculated status equals current."""
        req = make_request(request_id="req-1", status="PROCESSING")
        jobs = [
            SimpleNamespace(status="PROCESSING"),
            SimpleNamespace(status="QUEUED"),
        ]
        svc.job_repo.get_by_request.return_value = jobs

        svc._recalculate_request_status(req)
        svc.request_repo.update_status.assert_not_called()
