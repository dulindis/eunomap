import os
import pytest
from tests.test_database import create_test_engine, create_session


@pytest.fixture()
def db():
    engine, db_path = create_test_engine()
    SessionLocal = create_session(engine)

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()
        os.remove(db_path)
