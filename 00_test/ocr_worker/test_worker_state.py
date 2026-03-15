"""Unit tests for WorkerState (03_worker/app/core/state.py).

Pure logic tests -- no I/O, no mocks needed.

Test IDs: WS-001 through WS-010
"""

from datetime import datetime

import pytest

from app.core.state import WorkerState


# ---- WS-001: Initial state ----

def test_initial_state_is_idle():
    """WS-001: Fresh WorkerState has idle status, None job, zero counters."""
    state = WorkerState()

    assert state.status == "idle"
    assert state.current_job_id is None
    assert state.job_started_at is None
    assert state.files_completed == 0
    assert state.files_total == 0
    assert state.error_count == 0


# ---- WS-002: start_job ----

def test_start_job_sets_fields():
    """WS-002: start_job sets status, job_id, and started_at timestamp."""
    state = WorkerState()
    before = datetime.utcnow()

    state.start_job("job-abc")

    assert state.status == "processing"
    assert state.current_job_id == "job-abc"
    assert state.job_started_at is not None
    assert state.job_started_at >= before
    assert state.job_started_at <= datetime.utcnow()


# ---- WS-003: end_job resets and increments ----

def test_end_job_resets_and_increments():
    """WS-003: end_job clears job info, increments files_completed, returns to idle."""
    state = WorkerState()
    state.start_job("job-1")

    state.end_job()

    assert state.current_job_id is None
    assert state.job_started_at is None
    assert state.files_completed == 1
    assert state.status == "idle"


# ---- WS-004: Multiple end_job increments counter ----

def test_multiple_end_job_increments_counter():
    """WS-004: Each end_job call increments files_completed."""
    state = WorkerState()

    state.start_job("job-1")
    state.end_job()
    assert state.files_completed == 1

    state.start_job("job-2")
    state.end_job()
    assert state.files_completed == 2

    state.start_job("job-3")
    state.end_job()
    assert state.files_completed == 3


# ---- WS-005: record_error increments count and sets status ----

def test_record_error_increments_and_sets_status():
    """WS-005: record_error increments error_count and sets status to error."""
    state = WorkerState()

    state.record_error()

    assert state.error_count == 1
    assert state.status == "error"


# ---- WS-006: Multiple errors increment ----

def test_multiple_errors_increment_count():
    """WS-006: Each record_error call increments error_count."""
    state = WorkerState()

    state.record_error()
    state.record_error()
    state.record_error()

    assert state.error_count == 3
    assert state.status == "error"


# ---- WS-007: to_heartbeat idle state ----

def test_to_heartbeat_idle_state():
    """WS-007: to_heartbeat returns correct dict for idle state."""
    state = WorkerState()

    hb = state.to_heartbeat()

    assert hb == {
        "status": "idle",
        "current_job_id": None,
        "files_completed": 0,
        "files_total": 0,
        "error_count": 0,
    }


# ---- WS-008: to_heartbeat processing state ----

def test_to_heartbeat_processing_state():
    """WS-008: to_heartbeat returns correct dict while processing a job."""
    state = WorkerState()
    state.files_total = 5
    state.start_job("job-xyz")

    hb = state.to_heartbeat()

    assert hb == {
        "status": "processing",
        "current_job_id": "job-xyz",
        "files_completed": 0,
        "files_total": 5,
        "error_count": 0,
    }


# ---- WS-009: Lifecycle start -> end -> start ----

def test_lifecycle_start_end_start():
    """WS-009: State correctly transitions through start->end->start cycle."""
    state = WorkerState()

    # First job
    state.start_job("job-1")
    assert state.status == "processing"
    assert state.current_job_id == "job-1"

    state.end_job()
    assert state.status == "idle"
    assert state.current_job_id is None
    assert state.files_completed == 1

    # Second job
    state.start_job("job-2")
    assert state.status == "processing"
    assert state.current_job_id == "job-2"
    assert state.files_completed == 1  # not reset


# ---- WS-010: Lifecycle start -> error -> end ----

def test_lifecycle_start_error_end():
    """WS-010: Error during processing, then end_job still resets correctly."""
    state = WorkerState()

    state.start_job("job-err")
    assert state.status == "processing"

    state.record_error()
    assert state.status == "error"
    assert state.error_count == 1
    assert state.current_job_id == "job-err"  # job still tracked

    state.end_job()
    assert state.status == "idle"
    assert state.current_job_id is None
    assert state.files_completed == 1
    assert state.error_count == 1  # error count persists
