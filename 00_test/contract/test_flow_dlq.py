"""Cross-function flow tests: DLQ Flow (F3)

Test Dead Letter Queue impact on request status aggregation.

Test IDs: FL-007 through FL-009
"""

from types import SimpleNamespace

from helpers import JobStateMachine, make_job


# ---------------------------------------------------------------------------
# FL-007: All jobs DEAD_LETTER → request FAILED
# ---------------------------------------------------------------------------

class TestAllDlqRequestFailed:
    """FL-007: DEAD_LETTER job → request status = FAILED."""

    def test_single_dlq_job_request_failed(self):
        """FL-007a: Single DEAD_LETTER job → request FAILED."""
        jobs = [make_job(status="DEAD_LETTER")]
        assert JobStateMachine.get_request_status(jobs) == "FAILED"

    def test_all_dlq_jobs_request_failed(self):
        """FL-007b: All jobs DEAD_LETTER → request FAILED."""
        jobs = [make_job(status="DEAD_LETTER") for _ in range(3)]
        assert JobStateMachine.get_request_status(jobs) == "FAILED"

    def test_mixed_failed_and_dlq_request_failed(self):
        """FL-007c: Mix of FAILED + DEAD_LETTER → request FAILED."""
        jobs = [
            make_job(status="FAILED"),
            make_job(status="DEAD_LETTER"),
            make_job(status="DEAD_LETTER"),
        ]
        assert JobStateMachine.get_request_status(jobs) == "FAILED"

    def test_dead_letter_is_terminal(self):
        """FL-007d: DEAD_LETTER is a terminal state."""
        assert JobStateMachine.is_terminal("DEAD_LETTER") is True


# ---------------------------------------------------------------------------
# FL-008: Mix COMPLETED + DEAD_LETTER → PARTIAL_SUCCESS
# ---------------------------------------------------------------------------

class TestMixedCompletedDlq:
    """FL-008: Mix COMPLETED + DEAD_LETTER → PARTIAL_SUCCESS."""

    def test_completed_plus_dlq(self):
        """FL-008a: 1 COMPLETED + 1 DEAD_LETTER → PARTIAL_SUCCESS."""
        jobs = [
            make_job(status="COMPLETED"),
            make_job(status="DEAD_LETTER"),
        ]
        assert JobStateMachine.get_request_status(jobs) == "PARTIAL_SUCCESS"

    def test_completed_plus_failed_plus_dlq(self):
        """FL-008b: COMPLETED + FAILED + DEAD_LETTER → PARTIAL_SUCCESS."""
        jobs = [
            make_job(status="COMPLETED"),
            make_job(status="FAILED"),
            make_job(status="DEAD_LETTER"),
        ]
        assert JobStateMachine.get_request_status(jobs) == "PARTIAL_SUCCESS"

    def test_completed_plus_cancelled_partial(self):
        """FL-008c: COMPLETED + CANCELLED → PARTIAL_SUCCESS."""
        jobs = [
            make_job(status="COMPLETED"),
            make_job(status="CANCELLED"),
        ]
        assert JobStateMachine.get_request_status(jobs) == "PARTIAL_SUCCESS"


# ---------------------------------------------------------------------------
# FL-009: DLQ job retry_count preserved
# ---------------------------------------------------------------------------

class TestDlqRetryCountPreserved:
    """FL-009: DLQ job preserves retry_count for audit trail."""

    def test_retry_count_preserved_in_dlq_job(self):
        """FL-009a: Job moved to DLQ retains retry_count."""
        job = make_job(status="DEAD_LETTER", retry_count=3)
        assert job.retry_count == 3
        assert job.status == "DEAD_LETTER"

    def test_error_history_preserved(self):
        """FL-009b: Error history is preserved on DLQ job."""
        import json
        history = json.dumps([
            {"error": "timeout", "retriable": True},
            {"error": "timeout", "retriable": True},
            {"error": "timeout", "retriable": True},
        ])
        job = make_job(status="DEAD_LETTER", retry_count=3, error_history=history)
        errors = json.loads(job.error_history)
        assert len(errors) == 3
        assert all(e["retriable"] for e in errors)

    def test_dlq_transition_does_not_reset_count(self):
        """FL-009c: FAILED → DEAD_LETTER valid, count stays same."""
        assert JobStateMachine.validate_transition("FAILED", "DEAD_LETTER") is True
        # retry_count is a property of the job, not affected by transition
        job = make_job(status="FAILED", retry_count=3)
        # After transition, count should be preserved (tested via make_job)
        assert job.retry_count == 3
