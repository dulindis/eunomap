import os
import pytest
from tests.test_database import create_test_engine, create_session
from main import app, get_db
from fastapi.testclient import TestClient


@pytest.fixture()
def db():
    engine, db_path = create_test_engine()
    SessionLocal = create_session(engine)

    # start session
    session = SessionLocal()
    try:
        yield session
    finally:
        # rollback anything done in test
        session.rollback()
        session.close()
        # dispose engine
        engine.dispose()
        # remove temp DB file if it exists
        if os.path.exists(db_path):
            os.remove(db_path)


@pytest.fixture()
def client(db):
    # Override the dependency
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
