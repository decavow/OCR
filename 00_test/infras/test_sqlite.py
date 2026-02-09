"""
SQLite Database Infrastructure Test
Run: python test_sqlite.py
"""

import os
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime

# Configuration
DB_PATH = Path(__file__).parent.parent.parent / "data" / "ocr_platform.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"


class Base(DeclarativeBase):
    pass


class TestUser(Base):
    """Test table."""
    __tablename__ = "test_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def create_db_engine():
    """Create SQLite engine with WAL mode."""
    # Ensure directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )

    # Enable WAL mode
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def test_connection():
    """Test: Can connect to SQLite."""
    print("\n[TEST] SQLite Connection...")
    try:
        engine = create_db_engine()

        with engine.connect() as conn:
            result = conn.execute(text("SELECT sqlite_version()"))
            version = result.scalar()
            print(f"  [OK] Connected to SQLite")
            print(f"    - Version: {version}")
            print(f"    - Database: {DB_PATH}")

        return True
    except Exception as e:
        print(f"  [FAIL] Failed: {e}")
        return False


def test_wal_mode():
    """Test: WAL mode is enabled."""
    print("\n[TEST] WAL Mode...")
    try:
        engine = create_db_engine()

        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA journal_mode"))
            mode = result.scalar()
            print(f"  [OK] Journal mode: {mode}")

            if mode.lower() == "wal":
                print(f"    - WAL mode is correctly enabled")
                return True
            else:
                print(f"    - Expected WAL, got {mode}")
                return False
    except Exception as e:
        print(f"  [FAIL] Failed: {e}")
        return False


def test_create_table():
    """Test: Create and drop table."""
    print("\n[TEST] Create/Drop Table...")
    try:
        engine = create_db_engine()

        # Create table
        Base.metadata.create_all(bind=engine)
        print(f"  [OK] Created table: test_users")

        # Verify table exists
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='test_users'"
            ))
            if result.scalar():
                print(f"  [OK] Table verified in database")
            else:
                print(f"  [FAIL] Table not found")
                return False

        return True
    except Exception as e:
        print(f"  [FAIL] Failed: {e}")
        return False


def test_crud_operations():
    """Test: CRUD operations."""
    print("\n[TEST] CRUD Operations...")
    try:
        engine = create_db_engine()
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        # Create
        print("  Testing CREATE...")
        with SessionLocal() as session:
            user = TestUser(email="test@example.com")
            session.add(user)
            session.commit()
            session.refresh(user)
            user_id = user.id
            print(f"    [OK] Created user with ID: {user_id}")

        # Read
        print("  Testing READ...")
        with SessionLocal() as session:
            user = session.query(TestUser).filter(TestUser.id == user_id).first()
            if user:
                print(f"    [OK] Read user: {user.email}")
            else:
                print(f"    [FAIL] User not found")
                return False

        # Update
        print("  Testing UPDATE...")
        with SessionLocal() as session:
            user = session.query(TestUser).filter(TestUser.id == user_id).first()
            user.email = "updated@example.com"
            session.commit()
            print(f"    [OK] Updated email to: {user.email}")

        # Delete
        print("  Testing DELETE...")
        with SessionLocal() as session:
            user = session.query(TestUser).filter(TestUser.id == user_id).first()
            session.delete(user)
            session.commit()
            print(f"    [OK] Deleted user")

        return True
    except Exception as e:
        print(f"  [FAIL] Failed: {e}")
        return False


def test_cleanup():
    """Test: Cleanup test table."""
    print("\n[TEST] Cleanup...")
    try:
        engine = create_db_engine()

        # Drop test table
        Base.metadata.drop_all(bind=engine)
        print(f"  [OK] Dropped test table")

        return True
    except Exception as e:
        print(f"  [FAIL] Failed: {e}")
        return False


def main():
    print("=" * 60)
    print("SQLite Database Infrastructure Test")
    print("=" * 60)
    print(f"Database: {DATABASE_URL}")

    tests = [
        ("Connection", test_connection),
        ("WAL Mode", test_wal_mode),
        ("Create Table", test_create_table),
        ("CRUD Operations", test_crud_operations),
        ("Cleanup", test_cleanup),
    ]

    results = []
    for name, test_fn in tests:
        try:
            result = test_fn()
            results.append((name, result))
        except Exception as e:
            print(f"  [FAIL] Unexpected error: {e}")
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
        print("\n>>> All SQLite tests passed!")
        return 0
    else:
        print("\n>>> Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
