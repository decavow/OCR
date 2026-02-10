# cleanup_local_files() - MUST run after every job

import os
import shutil

from app.config import settings


def cleanup_local_files(job_id: str = None) -> None:
    """Clean up local temporary files after job completion."""
    temp_dir = settings.temp_dir

    if job_id:
        # Clean specific job directory
        job_dir = os.path.join(temp_dir, job_id)
        if os.path.exists(job_dir):
            shutil.rmtree(job_dir)
    else:
        # Clean entire temp directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            os.makedirs(temp_dir, exist_ok=True)


def ensure_temp_dir() -> None:
    """Ensure temp directory exists."""
    os.makedirs(settings.temp_dir, exist_ok=True)
