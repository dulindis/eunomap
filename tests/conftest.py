import os
import pytest
import io
import wave
import struct

from fastapi.testclient import TestClient

from main import app
from db import get_db
from tests.test_database import create_test_engine, create_session
from utils import add_tags

from utils.user_utils import add_users, SAMPLE_USERS
from utils.hierarchy_utils import load_hierarchy
from utils.tag_utils import add_tags, tag_processor
import pytest
import whisper


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
    add_users(SAMPLE_USERS, db)
    add_tags(test_hierarchy, db=db)
    db.commit()
    return db


# =============================================================================
# API Client Fixtures
# =============================================================================
@pytest.fixture()
def client(db, whisper_model=None):
    """
    FastAPI TestClient with database dependency override.
    Optionally override the Whisper model for faster tests or mocking.

    Args:
        db: Database session fixture
        whisper_model: Optional Whisper model to override main.model

    Yields:
        TestClient: Configured test client for API requests
    """
    app.dependency_overrides[get_db] = lambda: db

    if whisper_model is not None:
        global main_model
        main_model = whisper_model

    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def client_with_data(populated_db, whisper_model=None):
    """
    FastAPI TestClient with database dependency override.
    Optionally override the Whisper model for testing.
    """
    app.dependency_overrides[get_db] = lambda: populated_db

    if whisper_model is not None:
        global main_model
        main_model = whisper_model

    yield TestClient(app)
    app.dependency_overrides.clear()


# =============================================================================
# Test Data Fixtures
# =============================================================================
@pytest.fixture
def test_hierarchy_path():
    """Path to the test hierarchy JSON file."""
    # return "tests/test_hierarchy.json"
    # return "tests/hierarchy.json"
    return "tests/normed_hierarchy.json"


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
    return {tag_processor.normalize(name) for name in raw_tags}


@pytest.fixture
def sample_audio_path():
    path = "tests/test_note.wav"
    # Create a short silent WAV file if it doesn't exist
    if not os.path.exists(path):
        import wave
        import struct

        with wave.open(path, "w") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(16000)
            frames = [struct.pack("h", 0) for _ in range(16000)]
            f.writeframes(b"".join(frames))
    return path


@pytest.fixture(scope="session")
def whisper_model():
    model = whisper.load_model("small")  # load once
    return model


@pytest.fixture
def in_memory_audio():
    """
    Generates a 1-second silent WAV file in memory.
    Returns a BytesIO object ready for upload.
    """
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as f:
        f.setnchannels(1)  # mono
        f.setsampwidth(2)  # 2 bytes per sample
        f.setframerate(16000)  # 16kHz
        frames = [struct.pack("h", 0) for _ in range(16000)]
        f.writeframes(b"".join(frames))
    buffer.seek(0)  # reset cursor
    return buffer
