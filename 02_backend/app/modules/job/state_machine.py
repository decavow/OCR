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

    # Terminal status groups
    TERMINAL_SUCCESS = {"COMPLETED"}
    TERMINAL_FAILURE = {"FAILED", "DEAD_LETTER"}
    TERMINAL_CANCELLED = {"CANCELLED"}
    TERMINAL_ALL = TERMINAL_SUCCESS | TERMINAL_FAILURE | TERMINAL_CANCELLED
    IN_PROGRESS = {"PROCESSING", "QUEUED", "SUBMITTED", "VALIDATING"}

    @staticmethod
    def get_request_status(jobs: list) -> str:
        """
        Calculate request status from job statuses.

        Rules:
        1. No jobs -> "PROCESSING"
        2. Any job in PROCESSING/QUEUED/SUBMITTED/VALIDATING -> "PROCESSING"
        3. All COMPLETED -> "COMPLETED"
        4. All FAILED/DEAD_LETTER -> "FAILED"
        5. All CANCELLED -> "CANCELLED"
        6. Mix of terminal states -> "PARTIAL_SUCCESS"
        """
        if not jobs:
            return "PROCESSING"

        statuses = {j.status for j in jobs}

        # Any in-progress job means request is still processing
        if statuses & JobStateMachine.IN_PROGRESS:
            return "PROCESSING"

        # All terminal from here
        if statuses <= JobStateMachine.TERMINAL_SUCCESS:
            return "COMPLETED"

        if statuses <= JobStateMachine.TERMINAL_FAILURE:
            return "FAILED"

        if statuses <= JobStateMachine.TERMINAL_CANCELLED:
            return "CANCELLED"

        # Mix of terminal states
        return "PARTIAL_SUCCESS"
