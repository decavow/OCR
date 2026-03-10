"""
Test cases for M5: Background Scheduler (APScheduler)

Covers:
- Scheduler starts without errors
- Job registration and removal works
- Scheduler is an AsyncIOScheduler instance
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import importlib.util
scheduler_path = Path(__file__).parent.parent.parent / "02_backend" / "app" / "core" / "scheduler.py"


@pytest.fixture
def scheduler_module():
    """Load scheduler module with mocked dependencies, fresh scheduler each test."""
    logger_mock = MagicMock()
    with patch.dict("sys.modules", {
        "app.core.logging": MagicMock(get_logger=MagicMock(return_value=logger_mock)),
    }):
        spec = importlib.util.spec_from_file_location("scheduler", scheduler_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        mod.scheduler = AsyncIOScheduler()
        yield mod
        # Best-effort cleanup
        try:
            if mod.scheduler.running:
                mod.scheduler.shutdown(wait=False)
        except RuntimeError:
            pass


class TestScheduler:
    """Tests for scheduler init/shutdown."""

    @pytest.mark.asyncio
    async def test_scheduler_starts(self, scheduler_module):
        scheduler_module.init_scheduler()
        assert scheduler_module.scheduler.running is True

    @pytest.mark.asyncio
    async def test_scheduler_is_asyncio_scheduler(self, scheduler_module):
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        assert isinstance(scheduler_module.scheduler, AsyncIOScheduler)

    @pytest.mark.asyncio
    async def test_job_registration(self, scheduler_module):
        scheduler_module.init_scheduler()

        scheduler_module.scheduler.add_job(
            lambda: None, 'interval', seconds=3600, id='test_job'
        )
        job = scheduler_module.scheduler.get_job('test_job')
        assert job is not None
        assert job.id == 'test_job'

    @pytest.mark.asyncio
    async def test_job_removal(self, scheduler_module):
        scheduler_module.init_scheduler()

        scheduler_module.scheduler.add_job(
            lambda: None, 'interval', seconds=3600, id='removable_job'
        )
        scheduler_module.scheduler.remove_job('removable_job')
        assert scheduler_module.scheduler.get_job('removable_job') is None

    @pytest.mark.asyncio
    async def test_multiple_jobs(self, scheduler_module):
        scheduler_module.init_scheduler()

        scheduler_module.scheduler.add_job(
            lambda: None, 'interval', seconds=60, id='job_a'
        )
        scheduler_module.scheduler.add_job(
            lambda: None, 'interval', seconds=120, id='job_b'
        )
        jobs = scheduler_module.scheduler.get_jobs()
        job_ids = {j.id for j in jobs}
        assert 'job_a' in job_ids
        assert 'job_b' in job_ids
