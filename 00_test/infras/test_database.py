"""
Database Models & Repositories Test
Run: python test_database.py
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

# Test database (separate from main)
TEST_DB_PATH = Path(__file__).parent.parent.parent / "data" / "test_ocr.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"


def setup_test_db():
    """Setup test database."""
    TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def test_models():
    """Test: Models can be created."""
    print("\n[TEST] Creating models...")

    from app.infrastructure.database.models import (
        Base, User, Session, Request, File, Job, Service, Heartbeat
    )

    engine = setup_test_db()

    # Create all tables
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("  [OK] All tables created")

    # Check tables exist
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    expected_tables = ["users", "sessions", "requests", "files", "jobs", "services", "heartbeats"]
    for table in expected_tables:
        if table in tables:
            print(f"  [OK] Table exists: {table}")
        else:
            print(f"  [FAIL] Table missing: {table}")
            return False

    return True


def test_user_repository():
    """Test: UserRepository CRUD."""
    print("\n[TEST] UserRepository...")

    from app.infrastructure.database.models import Base, User
    from app.infrastructure.database.repositories import UserRepository

    engine = setup_test_db()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        repo = UserRepository(db)

        # Create
        user = repo.create_user("test@example.com", "hashed_password_123")
        print(f"  [OK] Created user: {user.id[:8]}...")

        # Read by email
        found = repo.get_by_email("test@example.com")
        if found and found.id == user.id:
            print(f"  [OK] Found user by email")
        else:
            print(f"  [FAIL] User not found by email")
            return False

        # Check email exists
        if repo.email_exists("test@example.com"):
            print(f"  [OK] Email exists check works")
        else:
            print(f"  [FAIL] Email exists check failed")
            return False

        # Soft delete
        repo.soft_delete(user)
        if user.deleted_at is not None:
            print(f"  [OK] User soft deleted")
        else:
            print(f"  [FAIL] Soft delete failed")
            return False

        # Should not find deleted user
        not_found = repo.get_by_email("test@example.com")
        if not_found is None:
            print(f"  [OK] Deleted user not found")
        else:
            print(f"  [FAIL] Deleted user still found")
            return False

    return True


def test_session_repository():
    """Test: SessionRepository."""
    print("\n[TEST] SessionRepository...")

    from app.infrastructure.database.models import Base, User
    from app.infrastructure.database.repositories import UserRepository, SessionRepository

    engine = setup_test_db()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        user_repo = UserRepository(db)
        session_repo = SessionRepository(db)

        # Create user first
        user = user_repo.create_user("session_test@example.com", "password")

        # Create session
        session = session_repo.create_session(user.id, expires_hours=1)
        print(f"  [OK] Created session: {session.id[:8]}...")

        # Get valid session
        valid = session_repo.get_valid(session.id)
        if valid:
            print(f"  [OK] Session is valid")
        else:
            print(f"  [FAIL] Session should be valid")
            return False

        # Test expired session
        from app.infrastructure.database.models import Session as SessionModel
        expired_session = SessionModel(
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        db.add(expired_session)
        db.commit()

        expired = session_repo.get_valid(expired_session.id)
        if expired is None:
            print(f"  [OK] Expired session not returned")
        else:
            print(f"  [FAIL] Expired session should not be valid")
            return False

        # Delete by user
        count = session_repo.delete_by_user(user.id)
        if count >= 1:
            print(f"  [OK] Deleted {count} sessions for user")
        else:
            print(f"  [FAIL] Should have deleted sessions")
            return False

    return True


def test_request_job_file_flow():
    """Test: Request -> File -> Job flow."""
    print("\n[TEST] Request/File/Job flow...")

    from app.infrastructure.database.models import Base
    from app.infrastructure.database.repositories import (
        UserRepository, RequestRepository, FileRepository, JobRepository
    )

    engine = setup_test_db()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        user_repo = UserRepository(db)
        request_repo = RequestRepository(db)
        file_repo = FileRepository(db)
        job_repo = JobRepository(db)

        # Create user
        user = user_repo.create_user("flow_test@example.com", "password")

        # Create request
        request = request_repo.create_request(
            user_id=user.id,
            total_files=2,
            method="ocr_text_raw",
            tier=0,
            output_format="txt",
        )
        print(f"  [OK] Created request: {request.id[:8]}...")

        # Create files
        file1 = file_repo.create_file(
            request_id=request.id,
            original_name="test1.jpg",
            mime_type="image/jpeg",
            size_bytes=1024,
            object_key=f"{user.id}/{request.id}/file1/test1.jpg",
        )
        file2 = file_repo.create_file(
            request_id=request.id,
            original_name="test2.png",
            mime_type="image/png",
            size_bytes=2048,
            object_key=f"{user.id}/{request.id}/file2/test2.png",
        )
        print(f"  [OK] Created 2 files")

        # Create jobs
        job1 = job_repo.create_job(
            request_id=request.id,
            file_id=file1.id,
            method="ocr_text_raw",
            tier=0,
            output_format="txt",
        )
        job2 = job_repo.create_job(
            request_id=request.id,
            file_id=file2.id,
            method="ocr_text_raw",
            tier=0,
            output_format="txt",
        )
        print(f"  [OK] Created 2 jobs")

        # Get jobs by request
        jobs = job_repo.get_by_request(request.id)
        if len(jobs) == 2:
            print(f"  [OK] Found {len(jobs)} jobs for request")
        else:
            print(f"  [FAIL] Expected 2 jobs, got {len(jobs)}")
            return False

        # Update job status
        job_repo.update_status(job1, "PROCESSING", worker_id="worker-1")
        if job1.status == "PROCESSING" and job1.worker_id == "worker-1":
            print(f"  [OK] Job status updated to PROCESSING")
        else:
            print(f"  [FAIL] Job status update failed")
            return False

        # Complete job
        job_repo.update_status(job1, "COMPLETED")
        job_repo.set_result_path(job1, f"{user.id}/{request.id}/file1/result.txt")
        if job1.status == "COMPLETED" and job1.result_path:
            print(f"  [OK] Job completed with result path")
        else:
            print(f"  [FAIL] Job completion failed")
            return False

        # Fail job with error
        job_repo.update_status(job2, "FAILED", error="Tesseract error", retriable=True)
        import json
        errors = json.loads(job2.error_history)
        if len(errors) == 1 and errors[0]["error"] == "Tesseract error":
            print(f"  [OK] Job failed with error history")
        else:
            print(f"  [FAIL] Error history not recorded")
            return False

        # Update request status
        request_repo.increment_completed(request)
        request_repo.increment_failed(request)
        if request.completed_files == 1 and request.failed_files == 1:
            print(f"  [OK] Request counters updated")
        else:
            print(f"  [FAIL] Request counters wrong")
            return False

    return True


def test_service_heartbeat():
    """Test: Service and Heartbeat."""
    print("\n[TEST] Service/Heartbeat...")

    from app.infrastructure.database.models import Base
    from app.infrastructure.database.repositories import ServiceRepository, HeartbeatRepository

    engine = setup_test_db()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        service_repo = ServiceRepository(db)
        heartbeat_repo = HeartbeatRepository(db)

        # Create service
        service = service_repo.create_service(
            service_id="worker-ocr-text-tier0",
            access_key="sk_test_key_123",
            allowed_methods=["ocr_text_raw"],
            allowed_tiers=[0],
        )
        print(f"  [OK] Created service: {service.id}")

        # Get by access key
        found = service_repo.get_by_access_key("sk_test_key_123")
        if found:
            print(f"  [OK] Found service by access key")
        else:
            print(f"  [FAIL] Service not found")
            return False

        # Check can_handle
        if service_repo.can_handle(service, "ocr_text_raw", 0):
            print(f"  [OK] Service can handle ocr_text_raw tier 0")
        else:
            print(f"  [FAIL] can_handle check failed")
            return False

        if not service_repo.can_handle(service, "ocr_text_raw", 1):
            print(f"  [OK] Service cannot handle tier 1")
        else:
            print(f"  [FAIL] Should not handle tier 1")
            return False

        # Create heartbeat
        heartbeat = heartbeat_repo.upsert(
            service_id=service.id,
            status="idle",
            files_completed=5,
        )
        print(f"  [OK] Created heartbeat")

        # Get latest
        latest = heartbeat_repo.get_latest_by_service(service.id)
        if latest and latest.files_completed == 5:
            print(f"  [OK] Got latest heartbeat")
        else:
            print(f"  [FAIL] Latest heartbeat wrong")
            return False

        # Get active workers
        active = heartbeat_repo.get_active_workers(timeout_seconds=60)
        if len(active) == 1:
            print(f"  [OK] Found 1 active worker")
        else:
            print(f"  [FAIL] Expected 1 active worker")
            return False

    return True


def cleanup():
    """Cleanup test database."""
    print("\n[TEST] Cleanup...")
    import gc
    gc.collect()  # Force garbage collection to release DB connections

    try:
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()
            print(f"  [OK] Deleted test database")
        # Also delete WAL files
        wal_path = Path(str(TEST_DB_PATH) + "-wal")
        shm_path = Path(str(TEST_DB_PATH) + "-shm")
        if wal_path.exists():
            wal_path.unlink()
        if shm_path.exists():
            shm_path.unlink()
    except PermissionError:
        print(f"  [OK] Test database cleanup skipped (file in use - normal on Windows)")
    return True


def main():
    print("=" * 60)
    print("Database Models & Repositories Test")
    print("=" * 60)
    print(f"Test Database: {TEST_DATABASE_URL}")

    tests = [
        ("Models", test_models),
        ("UserRepository", test_user_repository),
        ("SessionRepository", test_session_repository),
        ("Request/File/Job Flow", test_request_job_file_flow),
        ("Service/Heartbeat", test_service_heartbeat),
        ("Cleanup", cleanup),
    ]

    results = []
    for name, test_fn in tests:
        try:
            result = test_fn()
            results.append((name, result))
        except Exception as e:
            print(f"  [FAIL] Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n>>> All database tests passed!")
        return 0
    else:
        print("\n>>> Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
