"""Unit tests for JobStateMachine (02_backend/app/modules/job/state_machine.py).

Pure logic tests — no external dependencies.

Test IDs: SM-001 to SM-027
"""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------

BACKEND_ROOT = Path(__file__).parent.parent.parent / "02_backend"


def _load():
    mod_path = BACKEND_ROOT / "app" / "modules" / "job" / "state_machine.py"
    spec = importlib.util.spec_from_file_location("state_machine", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sm = _load()
JobStateMachine = sm.JobStateMachine
VALID_TRANSITIONS = sm.VALID_TRANSITIONS


def _jobs(*statuses: str) -> list:
    """Create a list of job-like objects from status strings."""
    return [SimpleNamespace(status=s) for s in statuses]


# ===================================================================
# get_request_status  (SM-001 to SM-016)
# ===================================================================


class TestGetRequestStatus:
    """SM-001 to SM-016: Aggregation of job statuses into request status."""

    def test_sm001_no_jobs_returns_processing(self):
        """SM-001: Empty job list -> PROCESSING."""
        assert JobStateMachine.get_request_status([]) == "PROCESSING"

    def test_sm002_all_completed(self):
        """SM-002: All COMPLETED -> COMPLETED."""
        assert JobStateMachine.get_request_status(_jobs("COMPLETED", "COMPLETED")) == "COMPLETED"

    def test_sm003_all_failed(self):
        """SM-003: All FAILED -> FAILED."""
        assert JobStateMachine.get_request_status(_jobs("FAILED", "FAILED")) == "FAILED"

    def test_sm004_all_dead_letter(self):
        """SM-004: All DEAD_LETTER -> FAILED."""
        assert JobStateMachine.get_request_status(_jobs("DEAD_LETTER", "DEAD_LETTER")) == "FAILED"

    def test_sm005_mixed_failed_and_dead_letter(self):
        """SM-005: Mix of FAILED + DEAD_LETTER -> FAILED (both in TERMINAL_FAILURE)."""
        assert JobStateMachine.get_request_status(_jobs("FAILED", "DEAD_LETTER")) == "FAILED"

    def test_sm006_all_cancelled(self):
        """SM-006: All CANCELLED -> CANCELLED."""
        assert JobStateMachine.get_request_status(_jobs("CANCELLED", "CANCELLED")) == "CANCELLED"

    def test_sm007_completed_and_failed_mix(self):
        """SM-007: COMPLETED + FAILED -> PARTIAL_SUCCESS."""
        assert JobStateMachine.get_request_status(_jobs("COMPLETED", "FAILED")) == "PARTIAL_SUCCESS"

    def test_sm008_completed_and_cancelled_mix(self):
        """SM-008: COMPLETED + CANCELLED -> PARTIAL_SUCCESS."""
        assert JobStateMachine.get_request_status(_jobs("COMPLETED", "CANCELLED")) == "PARTIAL_SUCCESS"

    def test_sm009_failed_and_cancelled_mix(self):
        """SM-009: FAILED + CANCELLED -> PARTIAL_SUCCESS."""
        assert JobStateMachine.get_request_status(_jobs("FAILED", "CANCELLED")) == "PARTIAL_SUCCESS"

    def test_sm010_any_processing_returns_processing(self):
        """SM-010: Any PROCESSING job -> PROCESSING."""
        assert JobStateMachine.get_request_status(_jobs("COMPLETED", "PROCESSING")) == "PROCESSING"

    def test_sm011_any_queued_returns_processing(self):
        """SM-011: Any QUEUED job -> PROCESSING."""
        assert JobStateMachine.get_request_status(_jobs("COMPLETED", "QUEUED")) == "PROCESSING"

    def test_sm012_any_submitted_returns_processing(self):
        """SM-012: Any SUBMITTED job -> PROCESSING."""
        assert JobStateMachine.get_request_status(_jobs("SUBMITTED")) == "PROCESSING"

    def test_sm013_any_validating_returns_processing(self):
        """SM-013: Any VALIDATING job -> PROCESSING."""
        assert JobStateMachine.get_request_status(_jobs("VALIDATING", "COMPLETED")) == "PROCESSING"

    def test_sm014_single_completed(self):
        """SM-014: Single COMPLETED job -> COMPLETED."""
        assert JobStateMachine.get_request_status(_jobs("COMPLETED")) == "COMPLETED"

    def test_sm015_single_failed(self):
        """SM-015: Single FAILED job -> FAILED."""
        assert JobStateMachine.get_request_status(_jobs("FAILED")) == "FAILED"

    def test_sm016_three_way_terminal_mix(self):
        """SM-016: COMPLETED + FAILED + CANCELLED -> PARTIAL_SUCCESS."""
        assert JobStateMachine.get_request_status(
            _jobs("COMPLETED", "FAILED", "CANCELLED")
        ) == "PARTIAL_SUCCESS"


# ===================================================================
# validate_transition  (SM-017 to SM-022)
# ===================================================================


class TestValidateTransition:
    """SM-017 to SM-022: State transition validation."""

    def test_sm017_submitted_to_validating(self):
        """SM-017: SUBMITTED -> VALIDATING is valid."""
        assert JobStateMachine.validate_transition("SUBMITTED", "VALIDATING") is True

    def test_sm018_submitted_to_completed_invalid(self):
        """SM-018: SUBMITTED -> COMPLETED is invalid (must go through PROCESSING)."""
        assert JobStateMachine.validate_transition("SUBMITTED", "COMPLETED") is False

    def test_sm019_processing_to_completed(self):
        """SM-019: PROCESSING -> COMPLETED is valid."""
        assert JobStateMachine.validate_transition("PROCESSING", "COMPLETED") is True

    def test_sm020_processing_to_failed(self):
        """SM-020: PROCESSING -> FAILED is valid."""
        assert JobStateMachine.validate_transition("PROCESSING", "FAILED") is True

    def test_sm021_completed_to_anything_invalid(self):
        """SM-021: COMPLETED -> any state is invalid (terminal)."""
        assert JobStateMachine.validate_transition("COMPLETED", "PROCESSING") is False
        assert JobStateMachine.validate_transition("COMPLETED", "QUEUED") is False

    def test_sm022_failed_to_queued_retry(self):
        """SM-022: FAILED -> QUEUED is valid (retry path)."""
        assert JobStateMachine.validate_transition("FAILED", "QUEUED") is True


# ===================================================================
# is_terminal  (SM-023 to SM-027)
# ===================================================================


class TestIsTerminal:
    """SM-023 to SM-027: Terminal status detection."""

    def test_sm023_completed_is_terminal(self):
        """SM-023: COMPLETED is terminal (empty transition set)."""
        assert JobStateMachine.is_terminal("COMPLETED") is True

    def test_sm024_processing_not_terminal(self):
        """SM-024: PROCESSING is not terminal."""
        assert JobStateMachine.is_terminal("PROCESSING") is False

    def test_sm025_failed_not_terminal(self):
        """SM-025: FAILED is NOT terminal (can transition to QUEUED or DEAD_LETTER)."""
        assert JobStateMachine.is_terminal("FAILED") is False

    def test_sm026_partial_success_is_terminal(self):
        """SM-026: PARTIAL_SUCCESS is terminal (empty transition set)."""
        assert JobStateMachine.is_terminal("PARTIAL_SUCCESS") is True

    def test_sm027_rejected_is_terminal(self):
        """SM-027: REJECTED is terminal (empty transition set)."""
        assert JobStateMachine.is_terminal("REJECTED") is True
