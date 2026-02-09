# verify_access_key(), check_job_file_acl()

from sqlalchemy.orm import Session

from app.infrastructure.database.models import (
    ServiceType,
    ServiceTypeStatus,
    Job,
    File,
)
from app.infrastructure.database.repositories import (
    ServiceTypeRepository,
    JobRepository,
    FileRepository,
)
from .exceptions import AccessDenied, ServiceNotRegistered, FileNotInJob


def verify_access_key(db: Session, access_key: str) -> ServiceType:
    """
    Verify access key and return service type.

    Access key is generated per service type when admin approves.
    Only APPROVED types have valid access keys.
    """
    service_type_repo = ServiceTypeRepository(db)
    service_type = service_type_repo.get_by_access_key(access_key)

    if not service_type:
        raise ServiceNotRegistered("Invalid access key")

    if service_type.status != ServiceTypeStatus.APPROVED:
        raise ServiceNotRegistered(f"Service type is {service_type.status}, not APPROVED")

    return service_type


def check_job_file_acl(
    db: Session,
    job_id: str,
    file_id: str,
    service_type: ServiceType,
) -> tuple[Job, File]:
    """
    Check if service type can access file via job.

    Returns (job, file) if access is allowed.
    Raises appropriate exception otherwise.
    """
    job_repo = JobRepository(db)
    file_repo = FileRepository(db)
    service_type_repo = ServiceTypeRepository(db)

    # Find job
    job = job_repo.get_active(job_id)
    if not job:
        raise AccessDenied("Job not found or not active")

    # Verify file belongs to job
    if job.file_id != file_id:
        raise FileNotInJob()

    # Get file
    file = file_repo.get_active(file_id)
    if not file:
        raise AccessDenied("File not found or not active")

    # Verify service type can handle this job type
    if not service_type_repo.can_handle(service_type, job.method, job.tier):
        raise AccessDenied(
            f"Service type cannot handle method={job.method}, tier={job.tier}"
        )

    return job, file
