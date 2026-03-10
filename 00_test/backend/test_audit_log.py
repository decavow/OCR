"""
Test cases for WS4: AuditLog

Covers:
- AuditLogRepository.record() creates entry
- AuditLogRepository.query_by_entity() filters correctly
- AuditLogRepository.query_recent() returns ordered results
- Details JSON serialization/deserialization
"""

import json
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add backend to path for direct imports
backend_path = Path(__file__).parent.parent.parent / "02_backend"
sys.path.insert(0, str(backend_path))

# Mock app.config to avoid .env dependency
mock_settings = MagicMock()
mock_settings.database_url = "sqlite:///:memory:"
sys.modules["app.config"] = MagicMock(settings=mock_settings)
sys.modules["app.core.logging"] = MagicMock(get_logger=MagicMock(return_value=MagicMock()))

from app.infrastructure.database.models import Base, AuditLog
from app.infrastructure.database.repositories.audit_log import AuditLogRepository


@pytest.fixture
def db_session():
    """Create in-memory SQLite DB with audit_logs table."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def audit_repo(db_session):
    return AuditLogRepository(db_session)


class TestAuditLogRecord:
    def test_record_creates_entry(self, audit_repo):
        entry = audit_repo.record(
            actor_email="admin@test.com",
            action="APPROVE",
            entity_type="service_type",
            entity_id="ocr-text-tier0",
        )
        assert entry.id is not None
        assert entry.actor_email == "admin@test.com"
        assert entry.action == "APPROVE"
        assert entry.entity_type == "service_type"
        assert entry.entity_id == "ocr-text-tier0"
        assert entry.timestamp is not None

    def test_record_with_details(self, audit_repo):
        details = {"allowed_methods": ["ocr_text_raw", "structured_extract"]}
        entry = audit_repo.record(
            actor_email="admin@test.com",
            action="APPROVE",
            entity_type="service_type",
            entity_id="ocr-paddle-vl",
            details=details,
        )
        parsed = json.loads(entry.details)
        assert parsed["allowed_methods"] == ["ocr_text_raw", "structured_extract"]

    def test_record_with_request_id(self, audit_repo):
        entry = audit_repo.record(
            actor_email="admin@test.com",
            action="DELETE",
            entity_type="service_type",
            entity_id="ocr-old",
            request_id="req-abc-123",
        )
        assert entry.request_id == "req-abc-123"

    def test_record_without_optional_fields(self, audit_repo):
        entry = audit_repo.record(
            actor_email="admin@test.com",
            action="DISABLE",
            entity_type="service_type",
            entity_id="ocr-text",
        )
        assert entry.details is None
        assert entry.request_id is None


class TestAuditLogQueryByEntity:
    def test_filters_by_entity(self, audit_repo):
        audit_repo.record("admin@test.com", "APPROVE", "service_type", "type-a")
        audit_repo.record("admin@test.com", "DISABLE", "service_type", "type-a")
        audit_repo.record("admin@test.com", "APPROVE", "service_type", "type-b")

        results = audit_repo.query_by_entity("service_type", "type-a")
        assert len(results) == 2
        assert all(r.entity_id == "type-a" for r in results)

    def test_returns_empty_for_nonexistent(self, audit_repo):
        results = audit_repo.query_by_entity("service_type", "nonexistent")
        assert len(results) == 0

    def test_respects_limit(self, audit_repo):
        for i in range(10):
            audit_repo.record("admin@test.com", "ENABLE", "service_type", "type-x")

        results = audit_repo.query_by_entity("service_type", "type-x", limit=3)
        assert len(results) == 3

    def test_ordered_by_timestamp_desc(self, audit_repo):
        audit_repo.record("admin@test.com", "APPROVE", "service_type", "type-a")
        audit_repo.record("admin@test.com", "DISABLE", "service_type", "type-a")

        results = audit_repo.query_by_entity("service_type", "type-a")
        assert results[0].timestamp >= results[1].timestamp


class TestAuditLogQueryRecent:
    def test_returns_recent_entries(self, audit_repo):
        audit_repo.record("admin1@test.com", "APPROVE", "service_type", "type-a")
        audit_repo.record("admin2@test.com", "REJECT", "service_type", "type-b")
        audit_repo.record("admin1@test.com", "DELETE", "service_type", "type-c")

        results = audit_repo.query_recent(limit=50)
        assert len(results) == 3

    def test_respects_limit(self, audit_repo):
        for i in range(10):
            audit_repo.record("admin@test.com", "ENABLE", "service_type", f"type-{i}")

        results = audit_repo.query_recent(limit=5)
        assert len(results) == 5

    def test_ordered_by_timestamp_desc(self, audit_repo):
        audit_repo.record("admin@test.com", "APPROVE", "service_type", "first")
        audit_repo.record("admin@test.com", "REJECT", "service_type", "second")

        results = audit_repo.query_recent()
        assert results[0].timestamp >= results[1].timestamp
