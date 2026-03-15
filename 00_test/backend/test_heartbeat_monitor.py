"""Unit tests for HeartbeatMonitor (02_backend/app/modules/job/heartbeat_monitor.py).

Service-layer tests with mocked repositories and retry orchestrator.

Test IDs: HB-001 to HB-010
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
from conftest import make_job
sys.path.pop(0)


# ---------------------------------------------------------------------------
# Load HeartbeatMonitor module
# ---------------------------------------------------------------------------

def _load_heartbeat_monitor():
    mod_path = BACKEND_ROOT / "app" / "modules" / "job" / "heartbeat_monitor.py"
    spec = importlib.util.spec_from_file_location("heartbeat_monitor", mod_path)
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


hb_mod = _load_heartbeat_monitor()
HeartbeatMonitor = hb_mod.HeartbeatMonitor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_instance(instance_id="worker-1"):
    return SimpleNamespace(id=instance_id)


@pytest.fixture
def monitor():
    """Create HeartbeatMonitor with all repos and orchestrator mocked."""
    db = MagicMock()
    retry_orch = AsyncMock()
    m = HeartbeatMonitor(db, retry_orchestrator=retry_orch)
    m.instance_repo = MagicMock()
    m.heartbeat_repo = MagicMock()
    m.job_repo = MagicMock()
    return m


@pytest.fixture
def monitor_no_orch():
    """Create HeartbeatMonitor without retry orchestrator."""
    db = MagicMock()
    m = HeartbeatMonitor(db, retry_orchestrator=None)
    m.instance_repo = MagicMock()
    m.heartbeat_repo = MagicMock()
    m.job_repo = MagicMock()
    return m


# ===================================================================
# check_workers  (HB-001 to HB-002)
# ===================================================================

class TestCheckWorkers:
    """HB-001 to HB-002: Find dead workers."""

    @pytest.mark.asyncio
    async def test_hb001_returns_dead_worker_ids(self, monitor):
        """HB-001: Returns list of dead worker IDs from stale instances."""
        stale = [_make_instance("worker-1"), _make_instance("worker-2")]
        monitor.instance_repo.get_stale_instances.return_value = stale

        result = await monitor.check_workers()
        assert result == ["worker-1", "worker-2"]
        assert monitor.instance_repo.mark_dead.call_count == 2

    @pytest.mark.asyncio
    async def test_hb002_returns_empty_when_no_stale(self, monitor):
        """HB-002: Returns empty list when no stale instances."""
        monitor.instance_repo.get_stale_instances.return_value = []

        result = await monitor.check_workers()
        assert result == []
        monitor.instance_repo.mark_dead.assert_not_called()


# ===================================================================
# detect_stalled  (HB-003 to HB-005)
# ===================================================================

class TestDetectStalled:
    """HB-003 to HB-005: Find PROCESSING jobs on dead workers."""

    @pytest.mark.asyncio
    async def test_hb003_returns_stalled_jobs(self, monitor):
        """HB-003: Returns PROCESSING jobs from dead workers."""
        stale = [_make_instance("worker-1")]
        monitor.instance_repo.get_stale_instances.return_value = stale
        stalled_jobs = [make_job(job_id="j1", worker_id="worker-1")]
        monitor.job_repo.get_processing_by_worker.return_value = stalled_jobs

        result = await monitor.detect_stalled()
        assert len(result) == 1
        assert result[0].id == "j1"

    @pytest.mark.asyncio
    async def test_hb004_returns_empty_when_no_dead_workers(self, monitor):
        """HB-004: Returns empty list when no dead workers found."""
        monitor.instance_repo.get_stale_instances.return_value = []

        result = await monitor.detect_stalled()
        assert result == []
        monitor.job_repo.get_processing_by_worker.assert_not_called()

    @pytest.mark.asyncio
    async def test_hb005_aggregates_jobs_from_multiple_dead_workers(self, monitor):
        """HB-005: Aggregates stalled jobs from multiple dead workers."""
        stale = [_make_instance("worker-1"), _make_instance("worker-2")]
        monitor.instance_repo.get_stale_instances.return_value = stale
        monitor.job_repo.get_processing_by_worker.side_effect = [
            [make_job(job_id="j1", worker_id="worker-1")],
            [make_job(job_id="j2", worker_id="worker-2"), make_job(job_id="j3", worker_id="worker-2")],
        ]

        result = await monitor.detect_stalled()
        assert len(result) == 3


# ===================================================================
# recover_stalled_jobs  (HB-006 to HB-008)
# ===================================================================

class TestRecoverStalledJobs:
    """HB-006 to HB-008: Requeue stalled jobs via orchestrator."""

    @pytest.mark.asyncio
    async def test_hb006_calls_orchestrator_for_each_job(self, monitor):
        """HB-006: Calls retry_orchestrator.handle_failure for each stalled job."""
        jobs = [make_job(job_id="j1"), make_job(job_id="j2")]

        await monitor.recover_stalled_jobs(jobs)
        assert monitor.retry_orchestrator.handle_failure.await_count == 2

    @pytest.mark.asyncio
    async def test_hb007_does_nothing_without_orchestrator(self, monitor_no_orch):
        """HB-007: Does nothing when retry_orchestrator is None."""
        jobs = [make_job(job_id="j1")]

        # Should not raise
        await monitor_no_orch.recover_stalled_jobs(jobs)

    @pytest.mark.asyncio
    async def test_hb008_continues_on_single_job_failure(self, monitor):
        """HB-008: Continues processing other jobs if one fails."""
        jobs = [make_job(job_id="j1"), make_job(job_id="j2"), make_job(job_id="j3")]
        # First call raises, second and third succeed
        monitor.retry_orchestrator.handle_failure.side_effect = [
            Exception("orchestrator error"),
            None,
            None,
        ]

        await monitor.recover_stalled_jobs(jobs)
        # All three jobs should have been attempted
        assert monitor.retry_orchestrator.handle_failure.await_count == 3


# ===================================================================
# run_check  (HB-009 to HB-010)
# ===================================================================

class TestRunCheck:
    """HB-009 to HB-010: Full check cycle."""

    @pytest.mark.asyncio
    async def test_hb009_returns_summary_with_recoveries(self, monitor):
        """HB-009: Returns summary dict with stalled_recovered and heartbeats_cleaned."""
        stale = [_make_instance("worker-1")]
        monitor.instance_repo.get_stale_instances.return_value = stale
        stalled_jobs = [make_job(job_id="j1"), make_job(job_id="j2")]
        monitor.job_repo.get_processing_by_worker.return_value = stalled_jobs
        monitor.heartbeat_repo.cleanup_old.return_value = 5

        result = await monitor.run_check()
        assert result["stalled_recovered"] == 2
        assert result["heartbeats_cleaned"] == 5

    @pytest.mark.asyncio
    async def test_hb010_returns_zeros_when_nothing_to_do(self, monitor):
        """HB-010: Returns zeros when no stalled jobs and no old heartbeats."""
        monitor.instance_repo.get_stale_instances.return_value = []
        monitor.heartbeat_repo.cleanup_old.return_value = 0

        result = await monitor.run_check()
        assert result["stalled_recovered"] == 0
        assert result["heartbeats_cleaned"] == 0
