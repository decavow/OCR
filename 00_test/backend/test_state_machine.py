"""
Test cases for M1: JobStateMachine.get_request_status()

Covers all status aggregation rules:
- Empty jobs list
- All COMPLETED
- All FAILED / DEAD_LETTER
- All CANCELLED
- Mixed terminal states (PARTIAL_SUCCESS)
- In-progress jobs (PROCESSING, QUEUED, SUBMITTED, VALIDATING)
- validate_transition and is_terminal
"""

import pytest
import sys
from pathlib import Path
from types import SimpleNamespace

# Import state_machine directly to avoid triggering full app import chain
import importlib.util
state_machine_path = Path(__file__).parent.parent.parent / "02_backend" / "app" / "modules" / "job" / "state_machine.py"
spec = importlib.util.spec_from_file_location("state_machine", state_machine_path)
state_machine_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(state_machine_mod)
JobStateMachine = state_machine_mod.JobStateMachine


def make_jobs(*statuses: str) -> list:
    """Helper: create mock job objects with given statuses."""
    return [SimpleNamespace(status=s) for s in statuses]


class TestGetRequestStatus:
    """Tests for get_request_status() aggregation logic."""

    def test_empty_jobs_returns_processing(self):
        assert JobStateMachine.get_request_status([]) == "PROCESSING"

    def test_all_completed_returns_completed(self):
        jobs = make_jobs("COMPLETED", "COMPLETED", "COMPLETED")
        assert JobStateMachine.get_request_status(jobs) == "COMPLETED"

    def test_single_completed_returns_completed(self):
        jobs = make_jobs("COMPLETED")
        assert JobStateMachine.get_request_status(jobs) == "COMPLETED"

    def test_all_failed_returns_failed(self):
        jobs = make_jobs("FAILED", "FAILED")
        assert JobStateMachine.get_request_status(jobs) == "FAILED"

    def test_all_dead_letter_returns_failed(self):
        jobs = make_jobs("DEAD_LETTER", "DEAD_LETTER")
        assert JobStateMachine.get_request_status(jobs) == "FAILED"

    def test_mixed_failed_and_dead_letter_returns_failed(self):
        jobs = make_jobs("FAILED", "DEAD_LETTER", "FAILED")
        assert JobStateMachine.get_request_status(jobs) == "FAILED"

    def test_all_cancelled_returns_cancelled(self):
        jobs = make_jobs("CANCELLED", "CANCELLED")
        assert JobStateMachine.get_request_status(jobs) == "CANCELLED"

    def test_any_processing_returns_processing(self):
        jobs = make_jobs("COMPLETED", "PROCESSING", "FAILED")
        assert JobStateMachine.get_request_status(jobs) == "PROCESSING"

    def test_any_queued_returns_processing(self):
        jobs = make_jobs("COMPLETED", "QUEUED")
        assert JobStateMachine.get_request_status(jobs) == "PROCESSING"

    def test_any_submitted_returns_processing(self):
        jobs = make_jobs("SUBMITTED", "COMPLETED")
        assert JobStateMachine.get_request_status(jobs) == "PROCESSING"

    def test_any_validating_returns_processing(self):
        jobs = make_jobs("VALIDATING", "FAILED")
        assert JobStateMachine.get_request_status(jobs) == "PROCESSING"

    def test_completed_and_failed_returns_partial_success(self):
        jobs = make_jobs("COMPLETED", "FAILED")
        assert JobStateMachine.get_request_status(jobs) == "PARTIAL_SUCCESS"

    def test_completed_and_cancelled_returns_partial_success(self):
        jobs = make_jobs("COMPLETED", "CANCELLED")
        assert JobStateMachine.get_request_status(jobs) == "PARTIAL_SUCCESS"

    def test_completed_and_dead_letter_returns_partial_success(self):
        jobs = make_jobs("COMPLETED", "DEAD_LETTER")
        assert JobStateMachine.get_request_status(jobs) == "PARTIAL_SUCCESS"

    def test_failed_and_cancelled_returns_partial_success(self):
        jobs = make_jobs("FAILED", "CANCELLED")
        assert JobStateMachine.get_request_status(jobs) == "PARTIAL_SUCCESS"

    def test_all_terminal_mix_returns_partial_success(self):
        jobs = make_jobs("COMPLETED", "FAILED", "CANCELLED", "DEAD_LETTER")
        assert JobStateMachine.get_request_status(jobs) == "PARTIAL_SUCCESS"


class TestValidateTransition:
    """Tests for validate_transition()."""

    def test_valid_submitted_to_validating(self):
        assert JobStateMachine.validate_transition("SUBMITTED", "VALIDATING") is True

    def test_valid_processing_to_completed(self):
        assert JobStateMachine.validate_transition("PROCESSING", "COMPLETED") is True

    def test_valid_failed_to_queued_retry(self):
        assert JobStateMachine.validate_transition("FAILED", "QUEUED") is True

    def test_invalid_completed_to_processing(self):
        assert JobStateMachine.validate_transition("COMPLETED", "PROCESSING") is False

    def test_invalid_cancelled_to_queued(self):
        assert JobStateMachine.validate_transition("CANCELLED", "QUEUED") is False

    def test_unknown_status(self):
        assert JobStateMachine.validate_transition("UNKNOWN", "PROCESSING") is False


class TestIsTerminal:
    """Tests for is_terminal()."""

    def test_completed_is_terminal(self):
        assert JobStateMachine.is_terminal("COMPLETED") is True

    def test_failed_is_not_terminal(self):
        # FAILED can transition to QUEUED (retry) or DEAD_LETTER
        assert JobStateMachine.is_terminal("FAILED") is False

    def test_dead_letter_is_terminal(self):
        assert JobStateMachine.is_terminal("DEAD_LETTER") is True

    def test_processing_is_not_terminal(self):
        assert JobStateMachine.is_terminal("PROCESSING") is False

    def test_cancelled_is_terminal(self):
        assert JobStateMachine.is_terminal("CANCELLED") is True
