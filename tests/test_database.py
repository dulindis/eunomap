# import os
# from sqlalchemy import create_engine, text
# from sqlalchemy.orm import sessionmaker
# from database import Base

# # Use an in-memory SQLite database for tests
# TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

# engine = create_engine(
#     TEST_SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
# )
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# # Enable FK constraints in SQLite
# with engine.connect() as conn:
#     conn.execute(text("PRAGMA foreign_keys = ON"))
#     conn.execute(text("PRAGMA journal_mode = WAL"))

# # Create all tables
# Base.metadata.create_all(bind=engine)

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database import Base

# Use an in-memory SQLite database for tests
TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Enable FK constraints in SQLite
with engine.connect() as conn:
    conn.execute(text("PRAGMA foreign_keys = ON"))
    conn.execute(text("PRAGMA journal_mode = WAL"))

# Create all tables
Base.metadata.create_all(bind=engine)
