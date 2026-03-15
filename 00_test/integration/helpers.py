"""Shared helper functions for integration tests.

These are imported by test modules. conftest.py handles fixtures and setup.
"""

import sys
from pathlib import Path

# Ensure conftest setup has run (import triggers setup)
INTEGRATION_DIR = Path(__file__).parent
if str(INTEGRATION_DIR) not in sys.path:
    sys.path.insert(0, str(INTEGRATION_DIR))


def register_and_get_token(client, email="test@example.com", password="Test1234!"):
    """Register user via API and return auth token."""
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"Register failed: {resp.text}"
    return resp.json()["token"]


def auth_header(token):
    """Build Authorization header dict."""
    return {"Authorization": f"Bearer {token}"}


def create_user(db, email="test@example.com", password="Test1234!", is_admin=False):
    """Create a user directly via AuthService (real bcrypt hashing)."""
    from app.modules.auth.service import AuthService

    svc = AuthService(db)
    user = svc.register(email, password)
    if is_admin:
        user.is_admin = True
        db.commit()
        db.refresh(user)
    return user


def login_user(db, email="test@example.com", password="Test1234!"):
    """Login user, return (user, session)."""
    from app.modules.auth.service import AuthService

    svc = AuthService(db)
    return svc.login(email, password)


def create_approved_service_type(
    db,
    type_id="ocr-test-tier0",
    access_key="sk_test_integration_key",
    methods=None,
    tiers=None,
):
    """Create an APPROVED service type with access_key in DB."""
    from app.infrastructure.database.repositories import ServiceTypeRepository

    repo = ServiceTypeRepository(db)
    return repo.create_or_update(
        type_id=type_id,
        display_name=f"Integration Test: {type_id}",
        description="Auto-created for integration tests",
        allowed_methods=methods or ["ocr_paddle_text"],
        allowed_tiers=tiers or [0],
        status="APPROVED",
        access_key=access_key,
    )


def create_request_with_jobs(
    db, user_id, num_jobs=1, method="ocr_paddle_text", tier=0, job_status="QUEUED"
):
    """Create a request with files and jobs in the database.

    Returns (request, list_of_jobs).
    Jobs are created in SUBMITTED then transitioned to job_status.
    """
    from app.infrastructure.database.repositories import (
        RequestRepository,
        FileRepository,
        JobRepository,
    )

    req_repo = RequestRepository(db)
    file_repo = FileRepository(db)
    job_repo = JobRepository(db)

    request = req_repo.create_request(
        user_id=user_id,
        file_count=num_jobs,
        method=method,
        tier=tier,
    )

    jobs = []
    for i in range(num_jobs):
        f = file_repo.create_file(
            request_id=request.id,
            original_name=f"test_{i}.png",
            mime_type="image/png",
            size_bytes=1024 * (i + 1),
            object_key=f"users/{user_id}/{request.id}/f{i}/test_{i}.png",
        )
        job = job_repo.create_job(
            request_id=request.id,
            file_id=f.id,
            method=method,
            tier=tier,
        )
        # Transition through valid states to reach target status
        if job_status != "SUBMITTED":
            job_repo.update_status(job, status="QUEUED")
            if job_status not in ("SUBMITTED", "QUEUED"):
                job_repo.update_status(job, status=job_status)
        jobs.append(job)

    # Refresh to get updated state
    db.refresh(request)
    for j in jobs:
        db.refresh(j)

    return request, jobs
