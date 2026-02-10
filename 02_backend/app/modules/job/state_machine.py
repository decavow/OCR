# JobStateMachine: validate_transition(), get_request_status()

from typing import Set

# Valid state transitions
VALID_TRANSITIONS: dict[str, Set[str]] = {
    "SUBMITTED": {"VALIDATING", "REJECTED"},
    "VALIDATING": {"QUEUED", "REJECTED"},
    "QUEUED": {"PROCESSING", "CANCELLED"},
    "PROCESSING": {"COMPLETED", "PARTIAL_SUCCESS", "FAILED"},
    "FAILED": {"QUEUED", "DEAD_LETTER"},  # Retry or DLQ
    # Terminal states
    "COMPLETED": set(),
    "PARTIAL_SUCCESS": set(),
    "REJECTED": set(),
    "CANCELLED": set(),
    "DEAD_LETTER": set(),
}


class JobStateMachine:
    @staticmethod
    def validate_transition(current: str, target: str) -> bool:
        """Check if transition is valid."""
        valid_targets = VALID_TRANSITIONS.get(current, set())
        return target in valid_targets

    @staticmethod
    def is_terminal(status: str) -> bool:
        """Check if status is terminal."""
        return len(VALID_TRANSITIONS.get(status, set())) == 0

    @staticmethod
    def get_request_status(jobs: list) -> str:
        """Calculate request status from job statuses."""
        # TODO: Aggregate job statuses to determine request status
        # PROCESSING if any job is processing
        # COMPLETED if all completed
        # PARTIAL_SUCCESS if some completed, some failed
        # FAILED if all failed
        pass
