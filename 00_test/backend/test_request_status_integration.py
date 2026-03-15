"""Integration tests for request status recalculation.

Tests the integration of JobStateMachine.get_request_status() driving
request status updates through JobService._recalculate_request_status().

Uses the real JobStateMachine (pure logic) and mocked repositories.

Test IDs: RI-001 to RI-005
"""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BACKEND_ROOT = Path(__file__).parent.parent.parent / "02_backend"
TEST_DIR = Path(__file__).parent

# Import helpers from conftest
sys.path.insert(0, str(TEST_DIR))
from conftest import make_job, make_request
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
# Load JobService with mocked deps but real state_machine
# ---------------------------------------------------------------------------

def _load_job_service():
    mod_path = BACKEND_ROOT / "app" / "modules" / "job" / "service.py"
    spec = importlib.util.spec_from_file_location("job_service_ri", mod_path)
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
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def svc():
    """Create JobService with mocked repos and real state machine."""
    db = MagicMock()
    service = JobService(db)
    service.job_repo = MagicMock()
    service.request_repo = MagicMock()
    service.file_repo = MagicMock()
    return service


# ===================================================================
# Request status recalculation integration  (RI-001 to RI-005)
# ===================================================================

class TestRequestStatusIntegration:
    """RI-001 to RI-005: State machine + service layer integration for request status."""

    def test_ri001_all_completed_sets_completed(self, svc):
        """RI-001: 3 jobs all COMPLETED -> request status COMPLETED."""
        req = make_request(request_id="req-1", status="PROCESSING")
        jobs = [
            SimpleNamespace(status="COMPLETED"),
            SimpleNamespace(status="COMPLETED"),
            SimpleNamespace(status="COMPLETED"),
        ]
        svc.job_repo.get_by_request.return_value = jobs

        svc._recalculate_request_status(req)
        svc.request_repo.update_status.assert_called_once_with(req, "COMPLETED")

    def test_ri002_mixed_completed_and_failed_sets_partial(self, svc):
        """RI-002: 2/3 COMPLETED, 1 FAILED -> PARTIAL_SUCCESS."""
        req = make_request(request_id="req-2", status="PROCESSING")
        jobs = [
            SimpleNamespace(status="COMPLETED"),
            SimpleNamespace(status="COMPLETED"),
            SimpleNamespace(status="FAILED"),
        ]
        svc.job_repo.get_by_request.return_value = jobs

        svc._recalculate_request_status(req)
        svc.request_repo.update_status.assert_called_once_with(req, "PARTIAL_SUCCESS")

    def test_ri003_all_failed_sets_failed(self, svc):
        """RI-003: All 3 FAILED -> FAILED."""
        req = make_request(request_id="req-3", status="PROCESSING")
        jobs = [
            SimpleNamespace(status="FAILED"),
            SimpleNamespace(status="FAILED"),
            SimpleNamespace(status="FAILED"),
        ]
        svc.job_repo.get_by_request.return_value = jobs

        svc._recalculate_request_status(req)
        svc.request_repo.update_status.assert_called_once_with(req, "FAILED")

    def test_ri004_all_cancelled_sets_cancelled(self, svc):
        """RI-004: All CANCELLED -> CANCELLED."""
        req = make_request(request_id="req-4", status="PROCESSING")
        jobs = [
            SimpleNamespace(status="CANCELLED"),
            SimpleNamespace(status="CANCELLED"),
            SimpleNamespace(status="CANCELLED"),
        ]
        svc.job_repo.get_by_request.return_value = jobs

        svc._recalculate_request_status(req)
        svc.request_repo.update_status.assert_called_once_with(req, "CANCELLED")

    def test_ri005_completed_and_cancelled_sets_partial(self, svc):
        """RI-005: 1 COMPLETED + 2 CANCELLED -> PARTIAL_SUCCESS."""
        req = make_request(request_id="req-5", status="PROCESSING")
        jobs = [
            SimpleNamespace(status="COMPLETED"),
            SimpleNamespace(status="CANCELLED"),
            SimpleNamespace(status="CANCELLED"),
        ]
        svc.job_repo.get_by_request.return_value = jobs

        svc._recalculate_request_status(req)
        svc.request_repo.update_status.assert_called_once_with(req, "PARTIAL_SUCCESS")
