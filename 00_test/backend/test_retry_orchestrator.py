"""
Test cases for M3: RetryOrchestrator + DLQ

Covers:
- Retriable failure -> requeue
- Non-retriable failure -> DLQ
- Max retries exceeded -> DLQ
- Retry count increment
- NATS publish called with correct subject/message
"""

import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from types import SimpleNamespace
from pathlib import Path
import importlib.util


@pytest.fixture
def orchestrator_class():
    logger_mock = MagicMock()
    settings_mock = MagicMock()
    settings_mock.max_job_retries = 3

    mocked_modules = {
        "app.core.logging": MagicMock(get_logger=MagicMock(return_value=logger_mock)),
        "app.config": MagicMock(settings=settings_mock),
        "app.infrastructure.database.models": MagicMock(),
        "app.infrastructure.database.repositories": MagicMock(),
        "app.infrastructure.queue.messages": MagicMock(),
        "app.infrastructure.queue.subjects": MagicMock(),
    }

    # Load subjects for real
    subj_path = Path(__file__).parent.parent.parent / "02_backend" / "app" / "infrastructure" / "queue" / "subjects.py"
    spec_subj = importlib.util.spec_from_file_location("subjects", subj_path)
    subj_mod = importlib.util.module_from_spec(spec_subj)
    spec_subj.loader.exec_module(subj_mod)
    mocked_modules["app.infrastructure.queue.subjects"] = subj_mod

    # Load messages for real
    msg_path = Path(__file__).parent.parent.parent / "02_backend" / "app" / "infrastructure" / "queue" / "messages.py"
    spec_msg = importlib.util.spec_from_file_location("messages", msg_path)
    msg_mod = importlib.util.module_from_spec(spec_msg)
    spec_msg.loader.exec_module(msg_mod)
    mocked_modules["app.infrastructure.queue.messages"] = msg_mod

    with patch.dict("sys.modules", mocked_modules):
        orc_path = Path(__file__).parent.parent.parent / "02_backend" / "app" / "modules" / "job" / "orchestrator.py"
        spec = importlib.util.spec_from_file_location("orchestrator", orc_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        yield mod.RetryOrchestrator


def make_job(job_id="job-1", status="FAILED", retry_count=0, error_history="[]",
             method="ocr_text_raw", tier=0, file_id="file-1", request_id="req-1"):
    return SimpleNamespace(
        id=job_id, status=status, retry_count=retry_count,
        error_history=error_history, method=method, tier=tier,
        file_id=file_id, request_id=request_id, max_retries=3,
        request=SimpleNamespace(output_format="txt"),
    )


def make_file(object_key="user1/req1/file1/test.png"):
    return SimpleNamespace(object_key=object_key)


class TestDecideRetryOrDlq:
    def test_under_limit_retriable_returns_retry(self, orchestrator_class):
        orc = orchestrator_class(db=MagicMock())
        job = make_job(retry_count=0)
        assert orc.decide_retry_or_dlq(job, retriable=True) == "retry"

    def test_at_max_retries_returns_dlq(self, orchestrator_class):
        orc = orchestrator_class(db=MagicMock())
        job = make_job(retry_count=3)
        assert orc.decide_retry_or_dlq(job, retriable=True) == "dlq"

    def test_over_max_retries_returns_dlq(self, orchestrator_class):
        orc = orchestrator_class(db=MagicMock())
        job = make_job(retry_count=5)
        assert orc.decide_retry_or_dlq(job, retriable=True) == "dlq"

    def test_non_retriable_returns_dlq(self, orchestrator_class):
        orc = orchestrator_class(db=MagicMock())
        job = make_job(retry_count=0)
        assert orc.decide_retry_or_dlq(job, retriable=False) == "dlq"

    def test_non_retriable_last_error_returns_dlq(self, orchestrator_class):
        orc = orchestrator_class(db=MagicMock())
        history = json.dumps([{"error": "bad format", "retriable": False}])
        job = make_job(retry_count=0, error_history=history)
        assert orc.decide_retry_or_dlq(job, retriable=True) == "dlq"


class TestHandleFailure:
    @pytest.mark.asyncio
    async def test_retriable_requeues(self, orchestrator_class):
        queue = MagicMock()
        queue.publish = AsyncMock()
        orc = orchestrator_class(db=MagicMock(), queue=queue)
        orc.job_repo.increment_retry = MagicMock()
        orc.job_repo.update_status = MagicMock()
        orc.file_repo.get_active = MagicMock(return_value=make_file())

        job = make_job(retry_count=0)
        await orc.handle_failure(job, "timeout", retriable=True)

        orc.job_repo.increment_retry.assert_called_once()
        orc.job_repo.update_status.assert_called_once()
        queue.publish.assert_called_once()
        # Verify subject is ocr.ocr_text_raw.tier0
        call_args = queue.publish.call_args
        assert call_args[0][0] == "ocr.ocr_text_raw.tier0"

    @pytest.mark.asyncio
    async def test_non_retriable_moves_to_dlq(self, orchestrator_class):
        queue = MagicMock()
        queue.publish = AsyncMock()
        orc = orchestrator_class(db=MagicMock(), queue=queue)
        orc.job_repo.update_status = MagicMock()
        orc.file_repo.get_active = MagicMock(return_value=make_file())

        job = make_job(retry_count=0)
        await orc.handle_failure(job, "invalid input", retriable=False)

        orc.job_repo.update_status.assert_called_once()
        call_args = queue.publish.call_args
        # Should use DLQ subject
        assert call_args[0][0] == "dlq.ocr_text_raw.tier0"

    @pytest.mark.asyncio
    async def test_max_retries_moves_to_dlq(self, orchestrator_class):
        queue = MagicMock()
        queue.publish = AsyncMock()
        orc = orchestrator_class(db=MagicMock(), queue=queue)
        orc.job_repo.update_status = MagicMock()
        orc.file_repo.get_active = MagicMock(return_value=make_file())

        job = make_job(retry_count=3)
        await orc.handle_failure(job, "still failing", retriable=True)

        call_args = queue.publish.call_args
        assert call_args[0][0] == "dlq.ocr_text_raw.tier0"


class TestRequeueJob:
    @pytest.mark.asyncio
    async def test_requeue_increments_retry(self, orchestrator_class):
        queue = MagicMock()
        queue.publish = AsyncMock()
        orc = orchestrator_class(db=MagicMock(), queue=queue)
        orc.job_repo.increment_retry = MagicMock()
        orc.job_repo.update_status = MagicMock()
        orc.file_repo.get_active = MagicMock(return_value=make_file())

        job = make_job(retry_count=1)
        await orc.requeue_job(job)

        orc.job_repo.increment_retry.assert_called_once_with(job)
        orc.job_repo.update_status.assert_called_once_with(job, status="QUEUED")
        queue.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_requeue_without_queue_no_error(self, orchestrator_class):
        orc = orchestrator_class(db=MagicMock(), queue=None)
        orc.job_repo.increment_retry = MagicMock()
        orc.job_repo.update_status = MagicMock()

        job = make_job()
        await orc.requeue_job(job)
        orc.job_repo.update_status.assert_called_once()


class TestMoveToDlq:
    @pytest.mark.asyncio
    async def test_dlq_sets_dead_letter_status(self, orchestrator_class):
        queue = MagicMock()
        queue.publish = AsyncMock()
        orc = orchestrator_class(db=MagicMock(), queue=queue)
        orc.job_repo.update_status = MagicMock()
        orc.file_repo.get_active = MagicMock(return_value=make_file())

        job = make_job()
        await orc.move_to_dlq(job)

        orc.job_repo.update_status.assert_called_once_with(job, status="DEAD_LETTER")
        queue.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_dlq_message_contains_job_info(self, orchestrator_class):
        queue = MagicMock()
        queue.publish = AsyncMock()
        orc = orchestrator_class(db=MagicMock(), queue=queue)
        orc.job_repo.update_status = MagicMock()
        orc.file_repo.get_active = MagicMock(return_value=make_file("uploads/test.png"))

        job = make_job(job_id="j-123", request_id="r-456", retry_count=3)
        await orc.move_to_dlq(job)

        msg = queue.publish.call_args[0][1]
        assert msg.job_id == "j-123"
        assert msg.request_id == "r-456"
        assert msg.retry_count == 3
        assert msg.object_key == "uploads/test.png"
