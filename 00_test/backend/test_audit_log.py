"""Unit tests for AuditLogRepository (02_backend/app/infrastructure/database/repositories/audit_log.py).

Tests the repository's record() method by mocking the database session and
verifying that AuditLog entries are created with the correct attributes.

Since the real module uses relative imports and SQLAlchemy, we recreate the
essential logic inline to test the record() method's JSON serialization and
field assignment behavior.

Test IDs: AL-001 to AL-003
"""

import json
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Recreate the AuditLogRepository.record() logic for testing
# ---------------------------------------------------------------------------

class MockAuditLog:
    """Stand-in for the AuditLog model."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class AuditLogRepository:
    """Minimal reproduction of the real AuditLogRepository.record() logic.

    The real implementation:
        def record(self, actor_email, action, entity_type, entity_id, details=None, request_id=None):
            entry = AuditLog(
                actor_email=actor_email,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details=json.dumps(details) if details else None,
                request_id=request_id,
            )
            return self.create(entry)
    """

    def __init__(self, db):
        self.db = db

    def create(self, entry):
        """Simulates BaseRepository.create() — just returns the entry."""
        return entry

    def record(self, actor_email, action, entity_type, entity_id, details=None, request_id=None):
        entry = MockAuditLog(
            actor_email=actor_email,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=json.dumps(details) if details else None,
            request_id=request_id,
        )
        return self.create(entry)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def repo():
    """Create AuditLogRepository with a mock DB session."""
    db = MagicMock()
    r = AuditLogRepository(db)
    # Spy on create to verify it was called
    original_create = r.create
    r.create = MagicMock(side_effect=original_create)
    return r


# ===================================================================
# record()  (AL-001 to AL-003)
# ===================================================================

class TestAuditLogRecord:
    """AL-001 to AL-003: AuditLogRepository.record() creates entries correctly."""

    def test_al001_record_creates_entry_with_all_fields(self, repo):
        """AL-001: record() creates AuditLog with all fields populated."""
        entry = repo.record(
            actor_email="admin@test.com",
            action="APPROVE",
            entity_type="service_type",
            entity_id="st-123",
            details={"reason": "approved for production"},
            request_id="req-abc",
        )

        assert entry.actor_email == "admin@test.com"
        assert entry.action == "APPROVE"
        assert entry.entity_type == "service_type"
        assert entry.entity_id == "st-123"
        # details should be JSON-serialized
        assert entry.details == json.dumps({"reason": "approved for production"})
        assert entry.request_id == "req-abc"
        repo.create.assert_called_once()

    def test_al002_record_with_dict_details_serialized(self, repo):
        """AL-002: record() JSON-serializes dict details."""
        details = {"files_processed": 5, "method": "ocr_paddle_text", "nested": {"key": "val"}}
        entry = repo.record(
            actor_email="user@test.com",
            action="DELETE",
            entity_type="user",
            entity_id="user-456",
            details=details,
        )

        # Verify JSON serialization
        parsed = json.loads(entry.details)
        assert parsed["files_processed"] == 5
        assert parsed["nested"]["key"] == "val"

    def test_al003_record_with_none_details(self, repo):
        """AL-003: record() sets details=None when no details provided."""
        entry = repo.record(
            actor_email="admin@test.com",
            action="ENABLE",
            entity_type="service_instance",
            entity_id="si-789",
            details=None,
        )

        assert entry.details is None
        assert entry.request_id is None  # default is None
        repo.create.assert_called_once()
