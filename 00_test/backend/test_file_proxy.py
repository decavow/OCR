"""Unit tests for FileProxyService (02_backend/app/modules/file_proxy/service.py).

Service-layer tests with mocked repositories, storage, and access control.

Test IDs: FP-001 to FP-006
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

sys.path.insert(0, str(TEST_DIR))
from conftest import make_job, make_file, make_request
sys.path.pop(0)


# ---------------------------------------------------------------------------
# Load FileProxyService module
# ---------------------------------------------------------------------------

def _load_file_proxy_service():
    mod_path = BACKEND_ROOT / "app" / "modules" / "file_proxy" / "service.py"
    # Use a dotted module name so the relative import `.access_control` resolves
    spec = importlib.util.spec_from_file_location(
        "app.modules.file_proxy.service", mod_path,
        submodule_search_locations=[],
    )
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "app.modules.file_proxy"

    settings_mock = MagicMock()
    settings_mock.minio_bucket_uploads = "uploads"
    settings_mock.minio_bucket_results = "results"

    # Mock access_control functions
    access_control_mock = MagicMock()

    # Mock generate_result_key
    storage_mock = MagicMock()
    storage_mock.generate_result_key = MagicMock(
        return_value="user-1/req-1/file-1/result.txt"
    )

    mocked = {
        "app": MagicMock(),
        "app.modules": MagicMock(),
        "app.modules.file_proxy": MagicMock(),
        "app.modules.file_proxy.access_control": access_control_mock,
        "app.modules.file_proxy.exceptions": MagicMock(),
        "app.core.logging": MagicMock(get_logger=MagicMock(return_value=MagicMock())),
        "app.config": MagicMock(settings=settings_mock),
        "app.infrastructure.database.models": MagicMock(),
        "app.infrastructure.database.repositories": MagicMock(),
        "app.infrastructure.storage": storage_mock,
        "sqlalchemy": MagicMock(),
        "sqlalchemy.orm": MagicMock(),
        "logging": MagicMock(),
    }
    with patch.dict("sys.modules", mocked):
        spec.loader.exec_module(mod)
    return mod, access_control_mock, storage_mock, settings_mock


fp_mod, ac_mock_module, storage_infra_mock, settings_mock = _load_file_proxy_service()
FileProxyService = fp_mod.FileProxyService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fp_svc():
    """Create FileProxyService with mocked storage and access control."""
    db = MagicMock()
    storage = MagicMock()
    storage.download = AsyncMock(return_value=b"file content bytes")
    storage.upload = AsyncMock()

    svc = FileProxyService(db, storage)
    svc.job_repo = MagicMock()

    return svc


@pytest.fixture(autouse=True)
def reset_ac_mocks():
    """Reset access control mocks before each test."""
    ac_mock_module.verify_access_key.reset_mock(side_effect=True)
    ac_mock_module.check_job_file_acl.reset_mock(side_effect=True)
    storage_infra_mock.generate_result_key.reset_mock(side_effect=True)
    yield


# ===================================================================
# download_for_worker  (FP-001 to FP-003)
# ===================================================================

class TestDownloadForWorker:
    """FP-001 to FP-003: Download file for worker processing."""

    @pytest.mark.asyncio
    async def test_fp001_downloads_file_successfully(self, fp_svc):
        """FP-001: Downloads file and returns (content, content_type, filename)."""
        service_type = SimpleNamespace(id="svc-1", status="APPROVED")
        job = make_job(job_id="job-1", file_id="file-1")
        file = make_file(
            file_id="file-1",
            original_name="document.png",
            mime_type="image/png",
            object_key="u1/r1/f1/document.png",
        )
        ac_mock_module.verify_access_key.return_value = service_type
        ac_mock_module.check_job_file_acl.return_value = (job, file)

        content, content_type, filename = await fp_svc.download_for_worker(
            "valid-key", "job-1", "file-1"
        )
        assert content == b"file content bytes"
        assert content_type == "image/png"
        assert filename == "document.png"

    @pytest.mark.asyncio
    async def test_fp002_verifies_access_key(self, fp_svc):
        """FP-002: Calls verify_access_key with the provided key."""
        service_type = SimpleNamespace(id="svc-1")
        job = make_job(job_id="job-1", file_id="file-1")
        file = make_file(file_id="file-1")
        ac_mock_module.verify_access_key.return_value = service_type
        ac_mock_module.check_job_file_acl.return_value = (job, file)

        await fp_svc.download_for_worker("my-access-key", "job-1", "file-1")
        ac_mock_module.verify_access_key.assert_called_once_with(
            fp_svc.db, "my-access-key"
        )

    @pytest.mark.asyncio
    async def test_fp003_raises_when_access_denied(self, fp_svc):
        """FP-003: Propagates exception when verify_access_key fails."""
        ac_mock_module.verify_access_key.side_effect = Exception("Invalid access key")

        with pytest.raises(Exception, match="Invalid access key"):
            await fp_svc.download_for_worker("bad-key", "job-1", "file-1")


# ===================================================================
# upload_from_worker  (FP-004 to FP-006)
# ===================================================================

class TestUploadFromWorker:
    """FP-004 to FP-006: Upload result from worker."""

    @pytest.mark.asyncio
    async def test_fp004_uploads_result_successfully(self, fp_svc):
        """FP-004: Uploads result and returns result_key."""
        service_type = SimpleNamespace(id="svc-1")
        req = make_request(request_id="req-1", user_id="user-1")
        job = make_job(job_id="job-1", file_id="file-1", request_id="req-1")
        # Attach request object to job (service accesses job.request)
        job.request = req
        file = make_file(file_id="file-1")

        ac_mock_module.verify_access_key.return_value = service_type
        ac_mock_module.check_job_file_acl.return_value = (job, file)
        storage_infra_mock.generate_result_key.return_value = "user-1/req-1/file-1/result.txt"

        result_key = await fp_svc.upload_from_worker(
            "valid-key", "job-1", "file-1",
            content=b"OCR result", content_type="text/plain",
        )
        assert result_key == "user-1/req-1/file-1/result.txt"
        fp_svc.storage.upload.assert_awaited_once()
        fp_svc.job_repo.set_result_path.assert_called_once_with(
            job, "user-1/req-1/file-1/result.txt"
        )

    @pytest.mark.asyncio
    async def test_fp005_generates_result_key_with_correct_params(self, fp_svc):
        """FP-005: Calls generate_result_key with user_id, request_id, file_id, output_format, original_name, method, created_at."""
        service_type = SimpleNamespace(id="svc-1")
        req = make_request(request_id="req-1", user_id="user-1", output_format="txt")
        job = make_job(job_id="job-1", file_id="file-1", request_id="req-1")
        job.request = req
        file = make_file(file_id="file-1", original_name="test.png")

        ac_mock_module.verify_access_key.return_value = service_type
        ac_mock_module.check_job_file_acl.return_value = (job, file)
        storage_infra_mock.generate_result_key.return_value = "u1/r1/f1/result.txt"

        await fp_svc.upload_from_worker(
            "valid-key", "job-1", "file-1",
            content=b"result", content_type="text/plain",
        )
        storage_infra_mock.generate_result_key.assert_called_once_with(
            user_id="user-1",
            request_id="req-1",
            file_id="file-1",
            output_format="txt",
            original_name="test.png",
            method="ocr_paddle_text",
            created_at=req.created_at,
        )

    @pytest.mark.asyncio
    async def test_fp006_raises_when_acl_check_fails(self, fp_svc):
        """FP-006: Propagates exception when check_job_file_acl fails."""
        service_type = SimpleNamespace(id="svc-1")
        ac_mock_module.verify_access_key.return_value = service_type
        ac_mock_module.check_job_file_acl.side_effect = Exception("File does not belong to job")

        with pytest.raises(Exception, match="File does not belong to job"):
            await fp_svc.upload_from_worker(
                "valid-key", "job-1", "wrong-file",
                content=b"data", content_type="text/plain",
            )
