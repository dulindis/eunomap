import os
import pytest
from fastapi.testclient import TestClient

from main import app, get_db
from tests.test_database import create_test_engine, create_session
from utils import add_tags, load_hierarchy, normalize


# =============================================================================
# Database Fixtures
# =============================================================================
@pytest.fixture()
def db():
    """
    Create a fresh test database session for each test.

    Yields:
        Session: SQLAlchemy session connected to temporary test database

    Cleanup:
        - Rolls back any changes
        - Closes session
        - Disposes engine
        - Removes temporary database file
    """
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


# =============================================================================
# API Client Fixtures
# =============================================================================
@pytest.fixture()
def client(db):
    """
    FastAPI TestClient with database dependency override.

    Args:
        db: Database session fixture

    Yields:
        TestClient: Configured test client for API requests
    """
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


# =============================================================================
# Test Data Fixtures
# =============================================================================
@pytest.fixture
def test_hierarchy_path():
    """Path to the test hierarchy JSON file."""
    return "tests/test_hierarchy.json"


@pytest.fixture
def test_hierarchy(test_hierarchy_path):
    """
    Load test hierarchy data from JSON file.

    Args:
        test_hierarchy_path: Path to test hierarchy file

    Returns:
        dict: Hierarchy data structure
    """
    return load_hierarchy(test_hierarchy_path)


@pytest.fixture
def expected_tag_names():
    """
    Set of normalized tag names expected in test hierarchy.

    Returns:
        set: Normalized tag names from the test hierarchy
    """
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
def populated_db(db, test_hierarchy):
    """
    Database pre-populated with test hierarchy tags.

    Args:
        db: Clean database session
        test_hierarchy: Test hierarchy data

    Returns:
        Session: Database session with test tags loaded
    """
    add_tags(test_hierarchy, db=db)
    db.commit()
    return db
