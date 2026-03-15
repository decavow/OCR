"""Shared utilities for contract & flow tests.

Loads REAL modules from both backend and worker with only I/O mocked.
"""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent.parent
BACKEND_ROOT = PROJECT_ROOT / "02_backend"
WORKER_ROOT = PROJECT_ROOT / "03_worker"

# Add worker to sys.path for direct imports
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))


# ---------------------------------------------------------------------------
# Backend module loaders
# ---------------------------------------------------------------------------

def load_backend_module(relative_path: str, module_name: str, extra_mocks=None):
    """Load a backend module with mocked I/O deps."""
    mod_path = BACKEND_ROOT / "app" / relative_path
    spec = importlib.util.spec_from_file_location(module_name, mod_path)
    mod = importlib.util.module_from_spec(spec)

    mocked = {
        "app.core.logging": MagicMock(get_logger=MagicMock(return_value=MagicMock())),
        "app.config": MagicMock(settings=MagicMock(max_job_retries=3)),
        "app.infrastructure.database.models": MagicMock(),
        "app.infrastructure.database.repositories": MagicMock(),
        "app.infrastructure.queue.nats_client": MagicMock(),
        "app.infrastructure.queue.messages": MagicMock(JobMessage=JobMessage),
        "app.infrastructure.queue.subjects": MagicMock(
            get_subject=get_subject,
            get_dlq_subject=get_dlq_subject,
        ),
        "app.infrastructure.storage.minio_client": MagicMock(),
        "sqlalchemy": MagicMock(),
        "sqlalchemy.orm": MagicMock(),
    }
    if extra_mocks:
        mocked.update(extra_mocks)
    with patch.dict("sys.modules", mocked):
        spec.loader.exec_module(mod)
    return mod


def load_backend_module_clean(relative_path: str, module_name: str):
    """Load a backend module that has no app-level deps (pure logic)."""
    mod_path = BACKEND_ROOT / "app" / relative_path
    spec = importlib.util.spec_from_file_location(module_name, mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Pre-loaded modules (used across many tests)
# ---------------------------------------------------------------------------

# Pure logic — no mocks needed
_sm_mod = load_backend_module_clean("modules/job/state_machine.py", "ct_state_machine")
JobStateMachine = _sm_mod.JobStateMachine
VALID_TRANSITIONS = _sm_mod.VALID_TRANSITIONS

_msg_mod = load_backend_module_clean("infrastructure/queue/messages.py", "ct_messages")
JobMessage = _msg_mod.JobMessage

_subj_mod = load_backend_module_clean("infrastructure/queue/subjects.py", "ct_subjects")
get_subject = _subj_mod.get_subject
get_dlq_subject = _subj_mod.get_dlq_subject


# ---------------------------------------------------------------------------
# Mock factories
# ---------------------------------------------------------------------------

def make_job(
    job_id="job-1",
    status="QUEUED",
    retry_count=0,
    error_history="[]",
    method="ocr_paddle_text",
    tier=0,
    request_id="req-1",
    file_id="file-1",
    result_path=None,
    worker_id=None,
    user_id="user-1",
    output_format="txt",
):
    return SimpleNamespace(
        id=job_id,
        status=status,
        retry_count=retry_count,
        error_history=error_history,
        method=method,
        tier=tier,
        request_id=request_id,
        file_id=file_id,
        result_path=result_path,
        worker_id=worker_id,
        request=SimpleNamespace(
            id=request_id,
            user_id=user_id,
            output_format=output_format,
        ),
    )


def make_request(
    request_id="req-1",
    user_id="user-1",
    status="PROCESSING",
    file_count=1,
    method="ocr_paddle_text",
    tier=0,
    output_format="txt",
):
    return SimpleNamespace(
        id=request_id,
        user_id=user_id,
        status=status,
        file_count=file_count,
        method=method,
        tier=tier,
        output_format=output_format,
    )


def make_file(
    file_id="file-1",
    request_id="req-1",
    original_name="test.png",
    mime_type="image/png",
    size_bytes=1024,
    object_key="user-1/req-1/file-1/test.png",
):
    return SimpleNamespace(
        id=file_id,
        request_id=request_id,
        original_name=original_name,
        mime_type=mime_type,
        size_bytes=size_bytes,
        object_key=object_key,
    )
