"""
Test cases for M4: HeartbeatMonitor + Stalled Job Recovery

Covers:
- Detect stale workers
- Detect stalled jobs on dead workers
- Recovery requeues jobs via RetryOrchestrator
- Cleanup old heartbeats
- No false positives (active workers not flagged)
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from types import SimpleNamespace
from pathlib import Path
import importlib.util


@pytest.fixture
def monitor_class():
    logger_mock = MagicMock()
    mocked_modules = {
        "app.core.logging": MagicMock(get_logger=MagicMock(return_value=logger_mock)),
        "app.infrastructure.database.models": MagicMock(),
        "app.infrastructure.database.repositories": MagicMock(),
    }
    with patch.dict("sys.modules", mocked_modules):
        mod_path = Path(__file__).parent.parent.parent / "02_backend" / "app" / "modules" / "job" / "heartbeat_monitor.py"
        spec = importlib.util.spec_from_file_location("heartbeat_monitor", mod_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        yield mod.HeartbeatMonitor


def make_instance(instance_id, status="ACTIVE"):
    return SimpleNamespace(id=instance_id, status=status)


def make_job(job_id, status="PROCESSING", worker_id="w1"):
    return SimpleNamespace(id=job_id, status=status, worker_id=worker_id)


class TestCheckWorkers:
    @pytest.mark.asyncio
    async def test_marks_stale_workers_dead(self, monitor_class):
        mon = monitor_class(db=MagicMock())
        stale_instances = [make_instance("w1"), make_instance("w2")]
        mon.instance_repo.get_stale_instances = MagicMock(return_value=stale_instances)
        mon.instance_repo.mark_dead = MagicMock()

        dead_ids = await mon.check_workers()
        assert dead_ids == ["w1", "w2"]
        assert mon.instance_repo.mark_dead.call_count == 2

    @pytest.mark.asyncio
    async def test_no_stale_workers(self, monitor_class):
        mon = monitor_class(db=MagicMock())
        mon.instance_repo.get_stale_instances = MagicMock(return_value=[])

        dead_ids = await mon.check_workers()
        assert dead_ids == []


class TestDetectStalled:
    @pytest.mark.asyncio
    async def test_finds_processing_jobs_on_dead_workers(self, monitor_class):
        mon = monitor_class(db=MagicMock())
        stale = [make_instance("w1")]
        jobs_on_w1 = [make_job("j1", worker_id="w1"), make_job("j2", worker_id="w1")]

        mon.instance_repo.get_stale_instances = MagicMock(return_value=stale)
        mon.instance_repo.mark_dead = MagicMock()
        mon.job_repo.get_processing_by_worker = MagicMock(return_value=jobs_on_w1)

        stalled = await mon.detect_stalled()
        assert len(stalled) == 2

    @pytest.mark.asyncio
    async def test_no_stalled_when_no_dead_workers(self, monitor_class):
        mon = monitor_class(db=MagicMock())
        mon.instance_repo.get_stale_instances = MagicMock(return_value=[])

        stalled = await mon.detect_stalled()
        assert stalled == []


class TestRecoverStalledJobs:
    @pytest.mark.asyncio
    async def test_recovery_calls_retry_orchestrator(self, monitor_class):
        orchestrator = MagicMock()
        orchestrator.handle_failure = AsyncMock()

        mon = monitor_class(db=MagicMock(), retry_orchestrator=orchestrator)
        jobs = [make_job("j1"), make_job("j2")]

        await mon.recover_stalled_jobs(jobs)

        assert orchestrator.handle_failure.call_count == 2
        # Verify called with retriable=True
        for call in orchestrator.handle_failure.call_args_list:
            assert call.kwargs.get("retriable", call.args[2] if len(call.args) > 2 else None) is True

    @pytest.mark.asyncio
    async def test_recovery_without_orchestrator_no_error(self, monitor_class):
        mon = monitor_class(db=MagicMock(), retry_orchestrator=None)
        jobs = [make_job("j1")]

        # Should not raise
        await mon.recover_stalled_jobs(jobs)

    @pytest.mark.asyncio
    async def test_recovery_handles_individual_failure(self, monitor_class):
        orchestrator = MagicMock()
        orchestrator.handle_failure = AsyncMock(side_effect=[None, Exception("queue error")])

        mon = monitor_class(db=MagicMock(), retry_orchestrator=orchestrator)
        jobs = [make_job("j1"), make_job("j2")]

        # Should not raise even if one job fails
        await mon.recover_stalled_jobs(jobs)
        assert orchestrator.handle_failure.call_count == 2


class TestRunCheck:
    @pytest.mark.asyncio
    async def test_full_cycle_with_stalled_jobs(self, monitor_class):
        orchestrator = MagicMock()
        orchestrator.handle_failure = AsyncMock()

        mon = monitor_class(db=MagicMock(), retry_orchestrator=orchestrator)
        stale = [make_instance("w1")]
        stalled_jobs = [make_job("j1")]

        mon.instance_repo.get_stale_instances = MagicMock(return_value=stale)
        mon.instance_repo.mark_dead = MagicMock()
        mon.job_repo.get_processing_by_worker = MagicMock(return_value=stalled_jobs)
        mon.heartbeat_repo.cleanup_old = MagicMock(return_value=5)

        result = await mon.run_check()
        assert result["stalled_recovered"] == 1
        assert result["heartbeats_cleaned"] == 5

    @pytest.mark.asyncio
    async def test_full_cycle_no_issues(self, monitor_class):
        mon = monitor_class(db=MagicMock())
        mon.instance_repo.get_stale_instances = MagicMock(return_value=[])
        mon.heartbeat_repo.cleanup_old = MagicMock(return_value=0)

        result = await mon.run_check()
        assert result["stalled_recovered"] == 0
        assert result["heartbeats_cleaned"] == 0
