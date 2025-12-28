import os
import pytest
from tests.test_database import create_test_engine, create_session
from main import app, get_db
from fastapi.testclient import TestClient

from utils import add_tags, load_hierarchy, normalize


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


@pytest.fixture
def expected_tag_names():
    raw_tags = [
        # top-level
        "Languages",
        "Health",
        "Pets",
        "Fitness",
        "Travel",
        "Wellness",
        "Technology",
        "Others",
        # Languages
        "English",
        "Spanish",
        # Health subtree
        "Doctors",
        "Cardiologists",
        "Dermatologist",
        "Nutrition",
        "Diet",
        "Supplements",
        "covid-19",
        # Pets
        "Dogs",
        "Cats",
        # Fitness
        "Workout",
        "Yoga",
        # Travel
        "Food",
        "Restaurants",
        "Cafes",
        "Tips & Tricks",
        "Travel Insurance",
        # Wellness
        "Meditation",
        "Mindfulness",
        " breathing Exercises ",
        # Technology
        "Technology",
        "Web Development",
        "AI/ML",
        "Equipment",
        "C#",
        "General",
    ]

    # Apply normalize() to all tags
    return {normalize(name) for name in raw_tags}


@pytest.fixture
def populated_db(db):
    hierarchy_data = load_hierarchy("tests/test_hierarchy.json")
    add_tags(hierarchy_data, db=db)
    db.commit()
    return db
