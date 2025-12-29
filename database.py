import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import StaticPool, create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")


if "sqlite" in SQLALCHEMY_DATABASE_URL:
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={
            "check_same_thread": False,
            "timeout": 30,  # Wait up to 30 seconds for lock to be released
        },
        poolclass=StaticPool,  # Use single connection pool for SQLite
    )
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)


# Enable foreign keys for SQLite
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Configure SQLite for better concurrent access."""
    if "sqlite" in SQLALCHEMY_DATABASE_URL:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")  # 30 second timeout
        cursor.close()


# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

# =============================================================================
# Database Operations
# =============================================================================


def init_db():
    """
    Initialize database by creating all tables if they don't exist.
    Safe to call multiple times - won't drop existing data.
    """
    import models

    print("Creating tables if they don't exist...")
    Base.metadata.create_all(bind=engine)


def reset_db():
    """
    Drop all tables and recreate them.
    ⚠️  WARNING: This deletes ALL data!
    """
    import models

    print("⚠️  Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    print("Creating fresh tables...")
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function for FastAPI routes.
    Provides a database session that automatically closes after use.

    Yields:
        Session: Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session():
    """
    Context manager for database sessions outside of FastAPI context.

    Usage:
        with get_db_session() as db:
            # Do database operations
            db.commit()

    Yields:
        Session: Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def load_initial_data(max_retries: int = 3):
    """
    Load initial data (hierarchy) into the database.
    Should be called during app startup.

    Args:
        max_retries: Number of retry attempts if database is locked
    """
    import time
    from sqlalchemy.exc import OperationalError
    from utils import load_hierarchy, add_tags

    for attempt in range(max_retries):
        try:
            with get_db_session() as db:
                hierarchy = load_hierarchy("hierarchy.json")
                add_tags(hierarchy, db=db)
                db.commit()
                print("✓ Hierarchy data loaded")
                return
        except OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                print(
                    f"⚠️  Database locked, retrying in 1s... ({attempt + 1}/{max_retries})"
                )
                time.sleep(1)
            else:
                print(f"❌ Failed to load hierarchy after {max_retries} attempts")
                raise


def dispose_engine():
    """
    Dispose of the database engine, closing all connections.
    Useful during application shutdown.
    """
    engine.dispose()
