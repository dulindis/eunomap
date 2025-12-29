import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import tempfile
from database import Base


def create_test_engine():
    db_fd, db_path = tempfile.mkstemp(suffix=".sqlite")
    os.close(db_fd)

    engine = create_engine(
        f"sqlite:///{db_path}",
        # "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )

    # SQLite pragmas
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))

    Base.metadata.create_all(bind=engine)
    return engine, db_path


def create_session(engine):
    return sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        future=True,
    )
