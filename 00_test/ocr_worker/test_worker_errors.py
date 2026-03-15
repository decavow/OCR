"""Unit tests for worker error classes and classify_error (03_worker/app/utils/errors.py).

Pure logic tests -- no I/O, no async.

Test IDs: WE-001 through WE-015
"""

import pytest

from app.utils.errors import (
    WorkerError,
    RetriableError,
    PermanentError,
    DownloadError,
    UploadError,
    OCRError,
    InvalidImageError,
    classify_error,
    RETRIABLE_ERRORS,
    NON_RETRIABLE_ERRORS,
)


# ---------------------------------------------------------------------------
# WE-001 to WE-005: isinstance / hierarchy checks
# ---------------------------------------------------------------------------

def test_download_error_is_retriable():
    """WE-001: DownloadError inherits from RetriableError and WorkerError."""
    err = DownloadError("download failed")
    assert isinstance(err, RetriableError)
    assert isinstance(err, WorkerError)
    assert isinstance(err, Exception)


def test_upload_error_is_retriable():
    """WE-002: UploadError inherits from RetriableError and WorkerError."""
    err = UploadError("upload failed")
    assert isinstance(err, RetriableError)
    assert isinstance(err, WorkerError)


def test_invalid_image_error_is_permanent():
    """WE-003: InvalidImageError inherits from PermanentError and WorkerError."""
    err = InvalidImageError("bad image")
    assert isinstance(err, PermanentError)
    assert isinstance(err, WorkerError)


def test_permanent_error_not_retriable():
    """WE-004: PermanentError is not a RetriableError."""
    err = PermanentError("permanent")
    assert not isinstance(err, RetriableError)
    assert isinstance(err, WorkerError)


def test_retriable_error_not_permanent():
    """WE-005: RetriableError is not a PermanentError."""
    err = RetriableError("retry me")
    assert not isinstance(err, PermanentError)
    assert isinstance(err, WorkerError)


# ---------------------------------------------------------------------------
# WE-006 to WE-014: classify_error tests
# ---------------------------------------------------------------------------

def test_classify_permanent_error():
    """WE-006: classify_error returns (msg, False) for PermanentError."""
    err = PermanentError("not recoverable")
    msg, retriable = classify_error(err)
    assert msg == "not recoverable"
    assert retriable is False


def test_classify_retriable_error():
    """WE-007: classify_error returns (msg, True) for RetriableError."""
    err = RetriableError("try again")
    msg, retriable = classify_error(err)
    assert msg == "try again"
    assert retriable is True


def test_classify_download_error():
    """WE-008: classify_error returns (msg, True) for DownloadError."""
    err = DownloadError("connection reset")
    msg, retriable = classify_error(err)
    assert msg == "connection reset"
    assert retriable is True


def test_classify_upload_error():
    """WE-009: classify_error returns (msg, True) for UploadError."""
    err = UploadError("timeout on upload")
    msg, retriable = classify_error(err)
    assert msg == "timeout on upload"
    assert retriable is True


def test_classify_invalid_image_error():
    """WE-010: classify_error returns (msg, False) for InvalidImageError."""
    err = InvalidImageError("corrupt png")
    msg, retriable = classify_error(err)
    assert msg == "corrupt png"
    assert retriable is False


def test_classify_value_error_by_name():
    """WE-011: classify_error returns (msg, False) for ValueError (name match)."""
    err = ValueError("bad value")
    msg, retriable = classify_error(err)
    assert msg == "bad value"
    assert retriable is False


def test_classify_connection_error_by_name():
    """WE-012: classify_error returns (msg, True) for ConnectionError (name match)."""
    err = ConnectionError("refused")
    msg, retriable = classify_error(err)
    assert msg == "refused"
    assert retriable is True


def test_classify_timeout_error_by_name():
    """WE-013: classify_error returns (msg, True) for TimeoutError (name match)."""
    err = TimeoutError("timed out")
    msg, retriable = classify_error(err)
    assert msg == "timed out"
    assert retriable is True


def test_classify_unknown_error_defaults_retriable():
    """WE-014: classify_error defaults to retriable for unknown error types."""
    err = RuntimeError("something unexpected")
    msg, retriable = classify_error(err)
    assert msg == "something unexpected"
    assert retriable is True


# ---------------------------------------------------------------------------
# WE-015: OCRError isinstance
# ---------------------------------------------------------------------------

def test_ocr_error_is_worker_error():
    """WE-015: OCRError inherits from WorkerError but not Retriable/Permanent."""
    err = OCRError("ocr failed")
    assert isinstance(err, WorkerError)
    assert not isinstance(err, RetriableError)
    assert not isinstance(err, PermanentError)
    # classify_error: OCRError is not in either list, defaults to retriable
    msg, retriable = classify_error(err)
    assert msg == "ocr failed"
    assert retriable is True
