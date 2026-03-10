# SQLite connection + WAL mode setup

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.config import settings

logger = logging.getLogger(__name__)

# Create engine with SQLite-specific settings
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,  # Set True for SQL debugging
)


# Enable WAL mode for better concurrency
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI - yields database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager for database session (non-FastAPI usage)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _run_migrations() -> None:
    """Run lightweight schema migrations for columns added after initial release.

    SQLAlchemy's create_all() only creates new tables; it does not add columns
    to existing tables.  We handle that here with ALTER TABLE statements,
    ignoring errors when the column already exists (SQLite raises
    OperationalError with 'duplicate column name').
    """
    from sqlalchemy import text

    migrations = [
        "ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0",
        'ALTER TABLE service_types ADD COLUMN supported_output_formats TEXT DEFAULT \'["txt","json"]\'',
        # audit_logs table is created by create_all(), but kept here as safety net
        """CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT (datetime('now')),
            actor_email VARCHAR(255) NOT NULL,
            action VARCHAR(50) NOT NULL,
            entity_type VARCHAR(50) NOT NULL,
            entity_id VARCHAR(150) NOT NULL,
            details TEXT,
            request_id VARCHAR(36)
        )""",
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_timestamp ON audit_logs(timestamp)",
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_actor_email ON audit_logs(actor_email)",
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_entity ON audit_logs(entity_type, entity_id)",
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs(action)",
    ]

    with engine.connect() as conn:
        for stmt in migrations:
            try:
                conn.execute(text(stmt))
                conn.commit()
                logger.info("Migration applied: %s", stmt[:80])
            except Exception as e:
                conn.rollback()
                logger.debug("Migration skipped (likely already applied): %s — %s", stmt[:60], e)


def init_db() -> None:
    """Initialize database - create all tables and run migrations."""
    from app.infrastructure.database.models import Base
    Base.metadata.create_all(bind=engine)
    _run_migrations()
    logger.info("Database initialized: %s", settings.database_url)


def drop_db() -> None:
    """Drop all tables (use with caution!)."""
    from app.infrastructure.database.models import Base
    Base.metadata.drop_all(bind=engine)
