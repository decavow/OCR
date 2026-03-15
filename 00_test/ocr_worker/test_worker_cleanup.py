"""Unit tests for cleanup utilities (03_worker/app/utils/cleanup.py).

Uses tmp_path fixture and mocks settings.temp_dir to avoid touching real filesystem.

Test IDs: CU-001 through CU-005
"""

import os
import shutil
from unittest.mock import patch, MagicMock

import pytest

from app.utils.cleanup import ensure_temp_dir, cleanup_local_files


# ---------------------------------------------------------------------------
# CU-001: ensure_temp_dir creates directory
# ---------------------------------------------------------------------------

def test_ensure_temp_dir_creates_dir(tmp_path):
    """CU-001: ensure_temp_dir creates the temp directory if it does not exist."""
    new_dir = tmp_path / "ocr_temp"
    assert not new_dir.exists()

    with patch("app.utils.cleanup.settings") as mock_settings:
        mock_settings.temp_dir = str(new_dir)
        ensure_temp_dir()

    assert new_dir.exists()
    assert new_dir.is_dir()


# ---------------------------------------------------------------------------
# CU-002: ensure_temp_dir already exists (no error)
# ---------------------------------------------------------------------------

def test_ensure_temp_dir_already_exists(tmp_path):
    """CU-002: ensure_temp_dir does not raise if directory already exists."""
    existing_dir = tmp_path / "ocr_temp"
    existing_dir.mkdir()
    assert existing_dir.exists()

    with patch("app.utils.cleanup.settings") as mock_settings:
        mock_settings.temp_dir = str(existing_dir)
        # Should not raise
        ensure_temp_dir()

    assert existing_dir.exists()
    assert existing_dir.is_dir()


# ---------------------------------------------------------------------------
# CU-003: cleanup_local_files with job_id removes only job directory
# ---------------------------------------------------------------------------

def test_cleanup_local_files_with_job_id(tmp_path):
    """CU-003: cleanup_local_files(job_id) removes only that job's subdirectory."""
    temp_dir = tmp_path / "ocr_temp"
    temp_dir.mkdir()

    # Create job directory with a file inside
    job_dir = temp_dir / "job-123"
    job_dir.mkdir()
    (job_dir / "result.txt").write_text("ocr result")

    # Create another job directory that should NOT be removed
    other_dir = temp_dir / "job-456"
    other_dir.mkdir()
    (other_dir / "other.txt").write_text("other result")

    with patch("app.utils.cleanup.settings") as mock_settings:
        mock_settings.temp_dir = str(temp_dir)
        cleanup_local_files(job_id="job-123")

    # job-123 should be gone
    assert not job_dir.exists()
    # job-456 should remain
    assert other_dir.exists()
    assert (other_dir / "other.txt").exists()
    # temp_dir itself should remain
    assert temp_dir.exists()


# ---------------------------------------------------------------------------
# CU-004: cleanup_local_files without job_id clears entire temp directory
# ---------------------------------------------------------------------------

def test_cleanup_local_files_without_job_id(tmp_path):
    """CU-004: cleanup_local_files() with no job_id clears and recreates temp dir."""
    temp_dir = tmp_path / "ocr_temp"
    temp_dir.mkdir()

    # Create multiple job directories
    (temp_dir / "job-1").mkdir()
    (temp_dir / "job-1" / "file.txt").write_text("data1")
    (temp_dir / "job-2").mkdir()
    (temp_dir / "job-2" / "file.txt").write_text("data2")

    with patch("app.utils.cleanup.settings") as mock_settings:
        mock_settings.temp_dir = str(temp_dir)
        cleanup_local_files(job_id=None)

    # temp_dir should exist but be empty (recreated)
    assert temp_dir.exists()
    assert list(temp_dir.iterdir()) == []


# ---------------------------------------------------------------------------
# CU-005: cleanup_local_files dir not exists (no error)
# ---------------------------------------------------------------------------

def test_cleanup_local_files_dir_not_exists(tmp_path):
    """CU-005: cleanup_local_files does not raise if temp dir does not exist."""
    nonexistent = tmp_path / "does_not_exist"
    assert not nonexistent.exists()

    with patch("app.utils.cleanup.settings") as mock_settings:
        mock_settings.temp_dir = str(nonexistent)
        # Should not raise for either case
        cleanup_local_files(job_id="job-999")
        cleanup_local_files(job_id=None)

    # Directory should still not exist (nothing to clean)
    assert not nonexistent.exists()
