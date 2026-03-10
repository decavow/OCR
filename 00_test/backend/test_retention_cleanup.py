"""
Test cases for M8: Retention Cleanup

Covers:
- Expired request detected
- Files moved to deleted bucket
- DB records soft-deleted
- Purge removes from storage permanently
- Non-expired requests not affected
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from types import SimpleNamespace
from pathlib import Path
import importlib.util


@pytest.fixture
def cleanup_class():
    logger_mock = MagicMock()
    mocked_modules = {
        "app.core.logging": MagicMock(get_logger=MagicMock(return_value=logger_mock)),
        "app.infrastructure.database.repositories": MagicMock(),
    }
    with patch.dict("sys.modules", mocked_modules):
        mod_path = Path(__file__).parent.parent.parent / "02_backend" / "app" / "modules" / "cleanup" / "service.py"
        spec = importlib.util.spec_from_file_location("cleanup_service", mod_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        yield mod.RetentionCleanupService


def make_request(request_id="req-1"):
    return SimpleNamespace(id=request_id, deleted_at=None)


def make_file(file_id="f1", object_key="user1/req1/f1/test.png"):
    return SimpleNamespace(id=file_id, object_key=object_key, deleted_at=None)


def make_job(job_id="j1", result_path="user1/req1/j1/result.txt"):
    return SimpleNamespace(id=job_id, result_path=result_path)


class TestCleanupExpired:
    @pytest.mark.asyncio
    async def test_no_expired_returns_zero(self, cleanup_class):
        svc = cleanup_class(db=MagicMock(), storage=None)
        svc.request_repo.get_expired = MagicMock(return_value=[])

        result = await svc.cleanup_expired()
        assert result["expired_requests"] == 0
        assert result["files_moved"] == 0

    @pytest.mark.asyncio
    async def test_expired_request_soft_deleted(self, cleanup_class):
        svc = cleanup_class(db=MagicMock(), storage=None)
        req = make_request()
        svc.request_repo.get_expired = MagicMock(return_value=[req])
        svc.file_repo.get_by_request = MagicMock(return_value=[make_file()])
        svc.file_repo.soft_delete = MagicMock()
        svc.job_repo.get_by_request = MagicMock(return_value=[])
        svc.request_repo.soft_delete = MagicMock()

        result = await svc.cleanup_expired()
        assert result["expired_requests"] == 1
        assert result["files_moved"] == 1
        svc.request_repo.soft_delete.assert_called_once_with(req)

    @pytest.mark.asyncio
    async def test_files_moved_with_storage(self, cleanup_class):
        storage = MagicMock()
        storage.uploads_bucket = "uploads"
        storage.deleted_bucket = "deleted"
        storage.client.copy_object = MagicMock()
        storage.client.remove_object = MagicMock()

        svc = cleanup_class(db=MagicMock(), storage=storage)
        req = make_request()
        files = [make_file("f1", "key1"), make_file("f2", "key2")]
        svc.request_repo.get_expired = MagicMock(return_value=[req])
        svc.file_repo.get_by_request = MagicMock(return_value=files)
        svc.file_repo.soft_delete = MagicMock()
        svc.job_repo.get_by_request = MagicMock(return_value=[])
        svc.request_repo.soft_delete = MagicMock()

        result = await svc.cleanup_expired()
        assert result["files_moved"] == 2

    @pytest.mark.asyncio
    async def test_multiple_expired_requests(self, cleanup_class):
        svc = cleanup_class(db=MagicMock(), storage=None)
        reqs = [make_request("r1"), make_request("r2"), make_request("r3")]
        svc.request_repo.get_expired = MagicMock(return_value=reqs)
        svc.file_repo.get_by_request = MagicMock(return_value=[make_file()])
        svc.file_repo.soft_delete = MagicMock()
        svc.job_repo.get_by_request = MagicMock(return_value=[])
        svc.request_repo.soft_delete = MagicMock()

        result = await svc.cleanup_expired()
        assert result["expired_requests"] == 3


class TestPurgeDeleted:
    @pytest.mark.asyncio
    async def test_no_soft_deleted_returns_zero(self, cleanup_class):
        svc = cleanup_class(db=MagicMock(), storage=None)
        svc.request_repo.get_soft_deleted_before = MagicMock(return_value=[])

        result = await svc.purge_deleted()
        assert result["purged_requests"] == 0

    @pytest.mark.asyncio
    async def test_purge_hard_deletes_from_db(self, cleanup_class):
        svc = cleanup_class(db=MagicMock(), storage=None)
        req = make_request()
        svc.request_repo.get_soft_deleted_before = MagicMock(return_value=[req])
        svc.file_repo.get_by_request_include_deleted = MagicMock(return_value=[])
        svc.request_repo.hard_delete = MagicMock()

        result = await svc.purge_deleted()
        assert result["purged_requests"] == 1
        svc.request_repo.hard_delete.assert_called_once_with(req)

    @pytest.mark.asyncio
    async def test_purge_removes_from_storage(self, cleanup_class):
        storage = MagicMock()
        storage.deleted_bucket = "deleted"
        storage.client.remove_object = MagicMock()

        svc = cleanup_class(db=MagicMock(), storage=storage)
        req = make_request()
        files = [make_file("f1", "key1")]
        svc.request_repo.get_soft_deleted_before = MagicMock(return_value=[req])
        svc.file_repo.get_by_request_include_deleted = MagicMock(return_value=files)
        svc.request_repo.hard_delete = MagicMock()

        result = await svc.purge_deleted()
        assert result["files_removed"] == 1
        storage.client.remove_object.assert_called_once()
