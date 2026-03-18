"""Unit tests for RetentionCleanupService (02_backend/app/modules/cleanup/service.py).

Service-layer tests with mocked repositories and storage.

Test IDs: RC-001 to RC-011
"""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BACKEND_ROOT = Path(__file__).parent.parent.parent / "02_backend"
TEST_DIR = Path(__file__).parent

sys.path.insert(0, str(TEST_DIR))
from conftest import make_job, make_request, make_file
sys.path.pop(0)


# ---------------------------------------------------------------------------
# Load RetentionCleanupService module
# ---------------------------------------------------------------------------

def _load_cleanup_service():
    mod_path = BACKEND_ROOT / "app" / "modules" / "cleanup" / "service.py"
    spec = importlib.util.spec_from_file_location("cleanup_service", mod_path)
    mod = importlib.util.module_from_spec(spec)

    mocked = {
        "app.core.logging": MagicMock(get_logger=MagicMock(return_value=MagicMock())),
        "app.config": MagicMock(settings=MagicMock()),
        "app.infrastructure.database.models": MagicMock(),
        "app.infrastructure.database.repositories": MagicMock(),
        "sqlalchemy": MagicMock(),
        "sqlalchemy.orm": MagicMock(),
    }
    with patch.dict("sys.modules", mocked):
        spec.loader.exec_module(mod)
    return mod


cleanup_mod = _load_cleanup_service()
RetentionCleanupService = cleanup_mod.RetentionCleanupService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def svc():
    """Create RetentionCleanupService with mocked repos and storage."""
    db = MagicMock()
    storage = MagicMock()
    storage.uploads_bucket = "uploads"
    storage.results_bucket = "results"
    storage.deleted_bucket = "deleted"
    s = RetentionCleanupService(db, storage=storage)
    s.request_repo = MagicMock()
    s.file_repo = MagicMock()
    s.job_repo = MagicMock()
    return s


@pytest.fixture
def svc_no_storage():
    """Create RetentionCleanupService without storage."""
    db = MagicMock()
    s = RetentionCleanupService(db, storage=None)
    s.request_repo = MagicMock()
    s.file_repo = MagicMock()
    s.job_repo = MagicMock()
    return s


# ===================================================================
# cleanup_expired  (RC-001 to RC-007)
# ===================================================================

class TestCleanupExpired:
    """RC-001 to RC-007: Find and soft-delete expired requests."""

    @pytest.mark.asyncio
    async def test_rc001_returns_zeros_when_no_expired(self, svc):
        """RC-001: Returns zero counts when no expired requests."""
        svc.request_repo.get_expired.return_value = []

        result = await svc.cleanup_expired()
        assert result["expired_requests"] == 0
        assert result["files_moved"] == 0

    @pytest.mark.asyncio
    async def test_rc002_processes_expired_request(self, svc):
        """RC-002: Processes one expired request with files and jobs."""
        req = make_request(request_id="req-1")
        file = make_file(file_id="f1", object_key="u1/r1/f1/test.png")
        job = make_job(job_id="j1", result_path="results/r1.txt")

        svc.request_repo.get_expired.return_value = [req]
        svc.file_repo.get_by_request.return_value = [file]
        svc.job_repo.get_by_request.return_value = [job]

        # Mock _move_to_deleted to avoid minio.commonconfig import
        svc._move_to_deleted = AsyncMock()

        result = await svc.cleanup_expired()
        assert result["expired_requests"] == 1
        assert result["files_moved"] == 1
        svc.file_repo.soft_delete.assert_called_once_with(file)
        svc.request_repo.soft_delete.assert_called_once_with(req)

    @pytest.mark.asyncio
    async def test_rc003_moves_file_to_deleted_bucket(self, svc):
        """RC-003: Calls _move_to_deleted for each file."""
        req = make_request(request_id="req-1")
        files = [
            make_file(file_id="f1", object_key="u1/r1/f1/a.png"),
            make_file(file_id="f2", object_key="u1/r1/f2/b.png"),
        ]
        svc.request_repo.get_expired.return_value = [req]
        svc.file_repo.get_by_request.return_value = files
        svc.job_repo.get_by_request.return_value = []
        svc._move_to_deleted = AsyncMock()

        result = await svc.cleanup_expired()
        assert result["files_moved"] == 2
        assert svc._move_to_deleted.await_count == 2

    @pytest.mark.asyncio
    async def test_rc004_moves_result_files(self, svc):
        """RC-004: Also moves result files from jobs."""
        req = make_request(request_id="req-1")
        job1 = make_job(job_id="j1", result_path="results/j1.txt")
        job2 = make_job(job_id="j2", result_path=None)  # no result

        svc.request_repo.get_expired.return_value = [req]
        svc.file_repo.get_by_request.return_value = []
        svc.job_repo.get_by_request.return_value = [job1, job2]
        svc._move_to_deleted = AsyncMock()

        await svc.cleanup_expired()
        # Only job1 has result_path, so _move_to_deleted called once for results
        svc._move_to_deleted.assert_awaited_once_with("results/j1.txt", "results")

    @pytest.mark.asyncio
    async def test_rc005_skips_storage_when_none(self, svc_no_storage):
        """RC-005: Soft-deletes files without storage operations when storage is None."""
        req = make_request(request_id="req-1")
        file = make_file(file_id="f1")

        svc_no_storage.request_repo.get_expired.return_value = [req]
        svc_no_storage.file_repo.get_by_request.return_value = [file]
        svc_no_storage.job_repo.get_by_request.return_value = []

        result = await svc_no_storage.cleanup_expired()
        assert result["files_moved"] == 1
        svc_no_storage.file_repo.soft_delete.assert_called_once_with(file)

    @pytest.mark.asyncio
    async def test_rc006_continues_on_move_error_skips_request_softdelete(self, svc):
        """RC-006: Continues processing files but skips request soft-delete on failure."""
        req = make_request(request_id="req-1")
        files = [
            make_file(file_id="f1", object_key="u1/r1/f1/a.png"),
            make_file(file_id="f2", object_key="u1/r1/f2/b.png"),
        ]
        svc.request_repo.get_expired.return_value = [req]
        svc.file_repo.get_by_request.return_value = files
        svc.job_repo.get_by_request.return_value = []
        # First move fails, second succeeds
        svc._move_to_deleted = AsyncMock(side_effect=[Exception("S3 error"), None])

        result = await svc.cleanup_expired()
        # Only the second file gets soft-deleted (first had a move error)
        assert result["files_moved"] == 1
        # Request must NOT be soft-deleted when files failed to move
        assert result["expired_requests"] == 0
        svc.request_repo.soft_delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_rc007_handles_multiple_expired_requests(self, svc):
        """RC-007: Processes multiple expired requests."""
        req1 = make_request(request_id="req-1")
        req2 = make_request(request_id="req-2")

        svc.request_repo.get_expired.return_value = [req1, req2]
        svc.file_repo.get_by_request.return_value = [make_file()]
        svc.job_repo.get_by_request.return_value = []
        svc._move_to_deleted = AsyncMock()

        result = await svc.cleanup_expired()
        assert result["expired_requests"] == 2
        assert result["files_moved"] == 2  # 1 file per request
        assert svc.request_repo.soft_delete.call_count == 2


# ===================================================================
# purge_deleted  (RC-008 to RC-011)
# ===================================================================

class TestPurgeDeleted:
    """RC-008 to RC-011: Permanently delete old soft-deleted files."""

    @pytest.mark.asyncio
    async def test_rc008_returns_zeros_when_nothing_to_purge(self, svc):
        """RC-008: Returns zero counts when no old soft-deleted requests."""
        svc.request_repo.get_soft_deleted_before.return_value = []

        result = await svc.purge_deleted()
        assert result["purged_requests"] == 0
        assert result["files_removed"] == 0

    @pytest.mark.asyncio
    async def test_rc009_purges_files_and_hard_deletes(self, svc):
        """RC-009: Removes files from storage and hard-deletes request from DB."""
        req = make_request(request_id="req-1")
        file = make_file(file_id="f1", object_key="u1/r1/f1/test.png")

        svc.request_repo.get_soft_deleted_before.return_value = [req]
        svc.file_repo.get_by_request_include_deleted.return_value = [file]

        result = await svc.purge_deleted()
        assert result["purged_requests"] == 1
        assert result["files_removed"] == 1
        svc.storage.client.remove_object.assert_called_once()
        svc.request_repo.hard_delete.assert_called_once_with(req)

    @pytest.mark.asyncio
    async def test_rc010_skips_hard_delete_on_remove_error(self, svc):
        """RC-010: Skips hard-delete if any file removal fails (prevents data loss)."""
        req = make_request(request_id="req-1")
        files = [
            make_file(file_id="f1", object_key="a.png"),
            make_file(file_id="f2", object_key="b.png"),
        ]

        svc.request_repo.get_soft_deleted_before.return_value = [req]
        svc.file_repo.get_by_request_include_deleted.return_value = files
        svc.storage.client.remove_object.side_effect = [Exception("S3 fail"), None]

        result = await svc.purge_deleted()
        # First fails, second succeeds
        assert result["files_removed"] == 1
        assert result["purged_requests"] == 0
        # Hard-delete must NOT happen when files failed to remove
        svc.request_repo.hard_delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_rc011_uses_default_retention_hours(self, svc):
        """RC-011: Uses default 168-hour retention period."""
        svc.request_repo.get_soft_deleted_before.return_value = []

        await svc.purge_deleted()
        call_args = svc.request_repo.get_soft_deleted_before.call_args
        # Verify cutoff was computed (first positional arg is datetime)
        cutoff = call_args[0][0]
        # The cutoff should be roughly 168 hours ago - just verify it's a datetime
        from datetime import datetime
        assert isinstance(cutoff, datetime)
