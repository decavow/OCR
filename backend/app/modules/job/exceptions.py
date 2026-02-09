# JobNotFound, InvalidTransition, AlreadyCancelled

from app.core.exceptions import AppException


class JobError(AppException):
    """Base job error."""
    pass


class JobNotFound(JobError):
    """Job not found."""
    def __init__(self, job_id: str):
        super().__init__(f"Job {job_id} not found", code="JOB_NOT_FOUND")


class RequestNotFound(JobError):
    """Request not found."""
    def __init__(self, request_id: str):
        super().__init__(f"Request {request_id} not found", code="REQUEST_NOT_FOUND")


class InvalidTransition(JobError):
    """Invalid status transition."""
    def __init__(self, current: str, target: str):
        super().__init__(
            f"Cannot transition from {current} to {target}",
            code="INVALID_TRANSITION"
        )


class AlreadyCancelled(JobError):
    """Request already cancelled."""
    def __init__(self):
        super().__init__("Request already cancelled", code="ALREADY_CANCELLED")
