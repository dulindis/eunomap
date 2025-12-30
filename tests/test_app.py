import os

from unittest.mock import patch
from sqlalchemy import select, func
from utils import (
    load_hierarchy,
    normalize,
    add_tags,
    get_or_create_tag,
    suggest_tags_from_text,
)
from models import Tag, Note, note_tags, tag_parents, User


def test_print_tags(populated_db):
    all_tags = populated_db.query(Tag).all()

    print("Tags currently in DB:")
    for t in all_tags:
        print(f"- {t.name}")

    # Optional: check total count
    print(f"Total tags: {len(all_tags)}")


def test_add_tags_creates_tags(populated_db, expected_tag_names):
    names = {t.name for t in populated_db.query(Tag).all()}
    assert names == expected_tag_names


def test_tag_parent_child_relationships(populated_db):
    doctor = populated_db.query(Tag).filter_by(name="doctor").one()
    health = populated_db.query(Tag).filter_by(name="health").one()
    fitness = populated_db.query(Tag).filter_by(name="fitness").one()

    assert doctor.parents == [health]
    assert doctor in health.children
    assert fitness.parents == []
    assert fitness.parents == [] or [p.name for p in fitness.parents] == ["others"]


def test_note_creation(populated_db):
    note = Note(content="test entry", media_type="text")
    populated_db.add(note)
    populated_db.commit()

    assert populated_db.query(Note).count() == 1


def test_note_tag_association(populated_db):
    # hierarchy_data = load_hierarchy("tests/test_hierarchy.json")
    # add_tags(hierarchy_data, db=populated_db)
    # populated_db.commit()

    note = Note(content="test", media_type="text")

    for name in [
        "health",
        "diet",
        "fitness",
        "doctors",
        "ai/ml",
        "c#",
        "tips & tricks",
    ]:
        tag = populated_db.query(Tag).filter_by(name=normalize(name)).one()
        note.tags.append(tag)

    populated_db.add(note)
    populated_db.commit()
    populated_db.refresh(note)

    assert len(note.tags) == 7

    rows = populated_db.execute(
        select(note_tags).where(note_tags.c.note_id == note.id)
    ).all()
    assert len(rows) == 7


def test_note_creates_missing_tag(populated_db):

    missing_tag_name = "NewTag"
    assert (
        populated_db.query(Tag).filter_by(name=normalize(missing_tag_name)).first()
        is None
    )

    note = Note(content="Test note with new tag", media_type="text")

    # Attach the tag: if add_tags logic is used in your app, you might call that here
    # For this test, we'll mimic auto-create behavior
    tag = populated_db.query(Tag).filter_by(name=normalize(missing_tag_name)).first()
    if tag is None:
        tag = Tag(name=normalize(missing_tag_name))
        populated_db.add(tag)
        populated_db.commit()
        populated_db.refresh(tag)

    note.tags.append(tag)
    populated_db.add(note)
    populated_db.commit()
    populated_db.refresh(note)

    # Assertions
    # 1️⃣ Note has the tag
    assert len(note.tags) == 1
    assert note.tags[0].name == normalize(missing_tag_name)

    # 2️⃣ Tag exists in DB
    tag_in_db = (
        populated_db.query(Tag)
        .filter_by(name=normalize(missing_tag_name))
        .one_or_none()
    )
    assert tag_in_db is not None
    assert tag_in_db.name == normalize(missing_tag_name)

    # 3️⃣ Association table has a row
    # row_count = db.execute(select("note_tags")).fetchall()
    rows = populated_db.execute(
        select(note_tags).where(note_tags.c.note_id == note.id)
    ).all()
    assert len(rows) == 1


def test_full_note_flow(populated_db):
    content = "test entry"
    media_type = "text"
    tags = ["health", "diet", "fitness", "doctors"]

    note = Note(content=content, media_type=media_type)

    for name in tags:
        tag = populated_db.query(Tag).filter_by(name=normalize(name)).first()
        assert tag is not None
        note.tags.append(tag)

    populated_db.add(note)
    populated_db.commit()
    populated_db.refresh(note)

    # ---------- ASSERTIONS ----------

    # only one note
    assert populated_db.query(Note).count() == 1

    # THIS note has exactly 4 tags
    assert len(note.tags) == 4
    tag_names = {t.name for t in note.tags}

    # association rows ONLY for this note
    rows = populated_db.execute(
        select(note_tags).where(note_tags.c.note_id == note.id)
    ).all()
    assert len(rows) == 4

    # ---- hierarchy assertions ----
    doctor = populated_db.query(Tag).filter_by(name="doctor").one()
    health = populated_db.query(Tag).filter_by(name="health").one()
    fitness = populated_db.query(Tag).filter_by(name="fitness").one()

    # doctors -> health
    assert doctor.parents == [health]
    assert doctor in health.children

    # fitness has no parents
    assert fitness.parents == []


def test_create_note_text(client):
    response = client.post("/notes/", data={"content": "hello", "tags": "health"})
    assert response.status_code == 200
    assert "id" in response.json()


def test_create_note_with_new_tag(populated_db, client):
    response = client.post(
        "/notes/",
        data={"content": "Test note", "tags": "newtag"},
    )

    assert response.status_code == 200
    data = response.json()
    note_id = data["id"]

    populated_db.expire_all()

    # --- Check note in DB ---
    note = populated_db.query(Note).filter_by(id=note_id).first()
    assert note is not None
    assert note.content == "Test note"

    # --- Check tag auto-created ---
    tag_name = normalize("newtag")
    tag = populated_db.query(Tag).filter_by(name=tag_name).first()
    print("Tag:", tag)
    print("Parents objects:", tag.parents)
    print("Parent names:", [p.name for p in tag.parents])

    rows = populated_db.execute(
        select(tag_parents).where(tag_parents.c.child_id == tag.id)
    ).all()
    print("Parent association rows:", rows)

    assert tag is not None
    assert tag.name == tag_name

    parents = [p.name for p in tag.parents]
    assert "others" in parents

    assert tag in note.tags

    # --- Optional: cleanup ---
    populated_db.delete(note)
    populated_db.delete(tag)
    populated_db.commit()


def test_create_note_without_content_or_file(client):
    response = client.post(
        "/notes/",
        data={"content": "", "tags": "health"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Note must contain text or an image."


def test_tag_hierarchy_no_duplicates_multiple_parents(populated_db):
    """Test that tags are not duplicated and can have multiple parents."""

    # Check no duplicate tag names
    tags = populated_db.query(Tag).all()
    tag_names = [t.name for t in tags]
    assert len(tag_names) == len(set(tag_names)), "Duplicate tags found"

    # Check specific tags with multiple parents
    health_tag = populated_db.query(Tag).filter_by(name="health").first()
    assert health_tag is not None

    # Health should appear as a child in multiple places:
    # - As a top-level category (no parent or 'others' as parent)
    # - Under "Pets"
    # - Under "Fitness"
    # So it should have multiple parent relationships OR appear in multiple contexts

    # Get all parent names for health
    health_parents = [p.name for p in health_tag.parents]
    print(f"Health tag parents: {health_parents}")

    # Health appears in: Pets list, Fitness list, Travel.Health dict
    # Depending on your hierarchy interpretation:
    # If "Health" in lists means linking to existing Health tag -> multiple parents
    # If "Health" at top level is different from "Health" in lists -> separate tags

    # Test "health" tag appears only once
    health_count = populated_db.query(Tag).filter_by(name="health").count()
    assert health_count == 1, f"Expected 1 health tag, found {health_count}"

    # Check Technology appears only once (both as top-level and in General list)
    technology_tag = populated_db.query(Tag).filter_by(name="technology").first()
    assert technology_tag is not None
    technology_count = populated_db.query(Tag).filter_by(name="technology").count()
    assert technology_count == 1, f"Expected 1 technology tag, found {technology_count}"

    # Technology should have 'general' as a parent (from the list)
    # AND possibly 'others' or no parent (from being top-level)
    tech_parents = [p.name for p in technology_tag.parents]
    print(f"Technology tag parents: {tech_parents}")

    # Check specific parent-child relationships

    # English and Spanish should have 'language' as parent
    english = populated_db.query(Tag).filter_by(name="english").first()
    spanish = populated_db.query(Tag).filter_by(name="spanish").first()
    assert english is not None
    assert spanish is not None
    assert "language" in [p.name for p in english.parents]
    assert "language" in [p.name for p in spanish.parents]

    # Cardiologist should have 'doctor' as parent
    cardiologist = populated_db.query(Tag).filter_by(name="cardiologist").first()
    assert cardiologist is not None
    assert "doctor" in [p.name for p in cardiologist.parents]

    # Doctor should have 'health' as parent
    doctor = populated_db.query(Tag).filter_by(name="doctor").first()
    assert doctor is not None
    assert "health" in [p.name for p in doctor.parents]

    # Diet should have 'nutrition' as parent
    diet = populated_db.query(Tag).filter_by(name="diet").first()
    assert diet is not None
    assert "nutrition" in [p.name for p in diet.parents]

    # Nutrition should have 'health' as parent
    nutrition = populated_db.query(Tag).filter_by(name="nutrition").first()
    assert nutrition is not None
    assert "health" in [p.name for p in nutrition.parents]

    # Check no duplicate parent relationships
    # Query tag_parents table directly
    all_relationships = populated_db.execute(
        select(tag_parents.c.child_id, tag_parents.c.parent_id)
    ).all()

    # Convert to set to check for duplicates
    relationship_tuples = [(r.child_id, r.parent_id) for r in all_relationships]
    assert len(relationship_tuples) == len(
        set(relationship_tuples)
    ), "Duplicate parent-child relationships found"

    # Check that specific tags have expected number of parents
    # Cats should have 'pet' as parent
    cats = populated_db.query(Tag).filter_by(name="cat").first()
    assert cats is not None
    cats_parents = [p.name for p in cats.parents]
    assert "pet" in cats_parents
    assert len(cats_parents) == 1, f"Cats should have 1 parent, has {len(cats_parents)}"

    # Web Development should have 'general' as parent
    web_dev = populated_db.query(Tag).filter_by(name="web_development").first()
    assert web_dev is not None
    assert "general" in [p.name for p in web_dev.parents]

    # General should have 'technology' as parent
    general = populated_db.query(Tag).filter_by(name="general").first()
    assert general is not None
    assert "technology" in [p.name for p in general.parents]

    print(f"\n✓ Total unique tags: {len(tags)}")
    print(f"✓ Total parent-child relationships: {len(all_relationships)}")
    print(f"✓ No duplicate tags or relationships found")


def test_reload_hierarchy_no_duplicates(populated_db, test_hierarchy):
    """Test that reloading hierarchy doesn't create duplicates."""

    # Get initial counts
    initial_tag_count = populated_db.query(Tag).count()
    initial_relationship_count = populated_db.execute(
        select(func.count()).select_from(tag_parents)
    ).scalar()

    print(f"Initial tags: {initial_tag_count}")
    print(f"Initial relationships: {initial_relationship_count}")

    # Reload the hierarchy (simulate app restart or manual reload)
    add_tags(test_hierarchy, db=populated_db)
    populated_db.commit()

    # Check counts haven't changed
    final_tag_count = populated_db.query(Tag).count()
    final_relationship_count = populated_db.execute(
        select(func.count()).select_from(tag_parents)
    ).scalar()

    print(f"Final tags: {final_tag_count}")
    print(f"Final relationships: {final_relationship_count}")

    assert (
        final_tag_count == initial_tag_count
    ), f"Tags increased from {initial_tag_count} to {final_tag_count} after reload"
    assert (
        final_relationship_count == initial_relationship_count
    ), f"Relationships increased from {initial_relationship_count} to {final_relationship_count} after reload"

    # Check still no duplicate tag names
    tags = populated_db.query(Tag).all()
    tag_names = [t.name for t in tags]
    assert len(tag_names) == len(set(tag_names)), "Duplicate tags found after reload"


def test_tag_can_have_multiple_parents(populated_db):
    """Test that a single tag can have multiple parents."""

    # Create a test scenario: add "health" as a child to multiple parents
    # (if not already in your hierarchy)

    fitness = populated_db.query(Tag).filter_by(name="fitness").first()
    pet = populated_db.query(Tag).filter_by(name="pet").first()

    # Create or get a tag that should have multiple parents
    test_tag = get_or_create_tag(
        populated_db, "multitag", parent=fitness, auto_others=False
    )
    populated_db.commit()

    # Add another parent
    test_tag = get_or_create_tag(
        populated_db, "multitag", parent=pet, auto_others=False
    )
    populated_db.commit()

    # Verify it has both parents
    populated_db.expire_all()
    # now refreshed data should be present
    test_tag = populated_db.query(Tag).filter_by(name="multitag").first()
    # list comprehension to get parent names
    parent_names = [p.name for p in test_tag.parents]

    # compare strings to strings
    print(f"Multitag parents: {parent_names}")
    assert "fitness" in parent_names
    assert "pet" in parent_names
    assert len(parent_names) == 2

    # Verify only one tag exists
    count = populated_db.query(Tag).filter_by(name="multitag").count()
    assert count == 1, f"Expected 1 multitag, found {count}"

    # Cleanup
    populated_db.delete(test_tag)
    populated_db.commit()


def test_debug_tag_creation(populated_db):
    """Debug what happens when we reload."""

    # Get initial state
    initial_tags = {t.name: t.id for t in populated_db.query(Tag).all()}
    print(f"\nInitial tags: {len(initial_tags)}")

    # Reload hierarchy
    hierarchy = load_hierarchy("hierarchy.json")
    add_tags(hierarchy, db=populated_db)
    populated_db.commit()

    # Check after
    final_tags = populated_db.query(Tag).all()
    print(f"Final tags: {len(final_tags)}")

    # Find duplicates
    from collections import Counter

    name_counts = Counter([t.name for t in final_tags])
    duplicates = {name: count for name, count in name_counts.items() if count > 1}

    if duplicates:
        print(f"\n❌ Duplicate tags found ({len(duplicates)} unique names):")
        for name, count in sorted(duplicates.items(), key=lambda x: x[1], reverse=True)[
            :20
        ]:
            print(f"  - '{name}': {count} copies")
            # Show the IDs
            ids = [t.id for t in final_tags if t.name == name]
            print(f"    IDs: {ids[:5]}...")  # Show first 5

    # Find completely new tags (not in initial set)
    new_tag_names = [t.name for t in final_tags if t.name not in initial_tags]
    if new_tag_names:
        print(f"\n❌ Completely new tags created ({len(new_tag_names)}):")
        for name in sorted(set(new_tag_names))[:20]:
            count = new_tag_names.count(name)
            print(f"  - '{name}' ({count} copies)")


"""
test_add_user: Directly manipulates the DB via SQLAlchemy ORM. 
It does not touch the FastAPI endpoint. 
Good for unit-testing ORM behavior, constraints, and relationships."""


def test_add_user_to_db(populated_db):
    # from models import User

    user = User(
        username="Ferrarinka",
        email="test@example.com",
        password_hash="hashedpassword",
        is_active=True,
    )
    populated_db.add(user)
    populated_db.commit()

    result = populated_db.query(User).filter_by(email="test@example.com").first()

    assert result is not None, "User should exist in the database"
    assert result.username == "Ferrarinka"
    assert result.is_active is True
    assert hasattr(result, "notes"), "User should have a notes relationship attribute"

    duplicate_user = User(
        username="Ferrarinka",  # same username
        email="another@example.com",
        password_hash="hash2",
    )
    populated_db.add(duplicate_user)
    try:
        populated_db.commit()
    except Exception as e:
        populated_db.rollback()
        assert "UNIQUE constraint" in str(e), "Duplicate username should raise an error"


"""
test_create_user_endpoint: Uses client.post(...) to simulate HTTP requests to your
 /users/ endpoint. This is an integration test because it tests the API route and the
   database together. 
This is what you want for testing signup behavior.
"""


def test_create_user_endpoint(client, populated_db):
    # from models import User

    # Step 1: Send a POST request to your "create user" endpoint
    response = client.post(
        "/users/",
        json={
            "username": "Ferrarinka",
            "email": "test@example.com",
            "password": "secret",
        },
    )

    # Step 2: Check HTTP response
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "Ferrarinka"
    assert data["email"] == "test@example.com"

    # Step 3: Verify user is really in the database
    user_in_db = populated_db.query(User).filter_by(email="test@example.com").first()
    assert user_in_db is not None
    assert user_in_db.username == "Ferrarinka"


def test_create_user_duplicate(client):
    # from models import User

    client.post(
        "/users/",
        json={
            "username": "Ferrarinka",
            "email": "test@example.com",
            "password": "secret",
        },
    )
    response = client.post(
        "/users/",
        json={
            "username": "Ferrarinka",
            "email": "test@example.com",
            "password": "secret",
        },
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_github_oauth(client, populated_db):
    from models import User

    # Patch GitHub API calls and the secret
    with patch("httpx.post") as mock_post, patch("httpx.get") as mock_get, patch(
        "main.Config.GITHUB_CLIENT_SECRET", "fake_secret"
    ), patch(
        "main.Config.GITHUB_CLIENT_ID", "fake_id"
    ):  # patch client ID too if needed

        # Mock responses
        mock_post.return_value.json.return_value = {"access_token": "token123"}
        mock_get.return_value.json.return_value = {
            "login": "ghuser",
            "email": "gh@example.com",
        }

        # Call the OAuth callback
        response = client.get("/auth/github/callback?code=fakecode")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "ghuser"
        assert data["email"] == "gh@example.com"

        # Verify the user was created in the DB
        user_in_db = populated_db.query(User).filter_by(email="gh@example.com").first()
        assert user_in_db is not None
        assert user_in_db.username == "ghuser"


def test_login_and_protected_endpoint(client, populated_db):
    from models import User
    from utils import hash_password

    # Add test user
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash=hash_password("secret"),
    )
    populated_db.add(user)
    populated_db.commit()

    # Login
    response = client.post(
        "/token", data={"username": "testuser", "password": "secret"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    assert token is not None

    # Use token to access protected endpoint
    response2 = client.post(
        "/notes/protected", json={"content": "JWT Note"}, headers={"token": token}
    )
    assert response2.status_code == 200
    assert response2.json()["content"] == "JWT Note"


@patch("main.model.transcribe")
def test_upload_audio_returns_structure(
    mock_transcribe, client_with_data, in_memory_audio
):
    from main import app
    from models import User
    from dependencies import get_current_user

    mock_transcribe.return_value = {
        "text": "hello world",
        "segments": [],
        "language": "en",
    }

    app.dependency_overrides[get_current_user] = lambda: User(id=1, username="alice123")

    response = client_with_data.post(
        "/upload_audio/",
        files={"file": ("test.wav", in_memory_audio, "audio/wav")},
        headers={"token": "x"},
    )

    assert response.status_code == 200
    data = response.json()

    assert "transcription" in data
    assert data["transcription"] == "hello world"
    assert "suggested_tags" in data
    assert isinstance(data["suggested_tags"], list)

    app.dependency_overrides.pop(get_current_user, None)


def test_suggest_tags_matches_existing_tags(populated_db):
    text = "This is about health and travel"

    tags = suggest_tags_from_text(text, populated_db)

    assert "health" in tags
    assert "travel" in tags


# def test_upload_audio_endpoint(client, populated_db, sample_audio_path, whisper_model):
#     """
#     Test /upload_audio/ endpoint with a sample audio file
#     and populated test tags in the database.
#     """
#     # Override get_db dependency to use populated_db
#     from main import model as main_model

#     main_model = whisper_model
#     from main import get_db, app

#     app.dependency_overrides[get_db] = lambda: populated_db

#     client = client(app)

#     # Use a test token for your get_current_user
#     headers = {"token": "test_token_for_user"}

#     with open(sample_audio_path, "rb") as f:
#         files = {"file": (os.path.basename(sample_audio_path), f, "audio/wav")}
#         response = client.post("/upload_audio/", files=files, headers=headers)

#     assert response.status_code == 200
#     data = response.json()
#     assert "transcription" in data
#     assert "tags" in data
#     assert isinstance(data["tags"], list)
#     print("Transcription:", data["transcription"])
#     print("Suggested tags:", data["tags"])


# @patch("main.model.transcribe")
# def test_upload_audio_mock_transcribe(
#     client, mock_transcribe, populated_db, sample_audio_path
# ):
#     mock_transcribe.return_value = {
#         "text": "This is a test note about health and travel"
#     }

#     from main import get_db, app

#     app.dependency_overrides[get_db] = lambda: populated_db
#     client = client(app)

#     headers = {"token": "test_token_for_user"}
#     with open(sample_audio_path, "rb") as f:
#         files = {"file": (os.path.basename(sample_audio_path), f, "audio/wav")}
#         response = client.post("/upload_audio/", files=files, headers=headers)

#     assert response.status_code == 200
#     data = response.json()
#     assert "health" in " ".join(data["tags"]).lower()
#     assert "travel" in " ".join(data["tags"]).lower()


# def test_upload_audio_endpoint(client, populated_db, sample_audio_path, whisper_model):
#     """
#     Test /upload_audio/ endpoint with real Whisper model and sample audio.
#     """
#     # Use the updated client fixture with whisper_model override
#     client = client(db=populated_db, whisper_model=whisper_model)

#     headers = {"token": "test_token_for_user"}
#     with open(sample_audio_path, "rb") as f:
#         files = {"file": (os.path.basename(sample_audio_path), f, "audio/wav")}
#         response = client.post("/upload_audio/", files=files, headers=headers)

#     assert response.status_code == 200
#     data = response.json()
#     assert "transcription" in data
#     assert "tags" in data
#     assert isinstance(data["tags"], list)
#     print("Transcription:", data["transcription"])
#     print("Suggested tags:", data["tags"])


# ------------------------------------------------------------------
# Test /upload_audio/ with mocked Whisper transcription
# ------------------------------------------------------------------
# working, but real model, not ok to use no ral resuls !!!!!
# def test_upload_audio_endpoint(client, in_memory_audio, whisper_model):
#     import main

#     main.model = whisper_model  # patch the global model for this test

#     # Override auth to avoid 401
#     from models import User

#     client.app.dependency_overrides[main.get_current_user] = lambda: User(
#         id=1, username="alice123"
#     )

#     headers = {"token": "anything"}
#     files = {"file": ("test_note.wav", in_memory_audio, "audio/wav")}
#     response = client.post("/upload_audio/", files=files, headers=headers)
#     print("STATUS:", response.status_code)
#     print("RESPONSE JSON:", response.json())
#     print("RESPONSE TEXT:", response.text)

#     assert response.status_code == 200


# @patch("main.model.transcribe")
# def test_upload_audio_mock_transcribe(
#     mock_transcribe, client_with_data, in_memory_audio
# ):
#     """
#     Test /upload_audio/ endpoint using mocked Whisper transcription.
#     """
#     from main import app
#     from dependencies import get_current_user

#     mock_transcribe.return_value = {
#         "text": "This is a test note about health and travel"
#     }

#     # Bypass authentication
#     app.dependency_overrides[get_current_user] = lambda: User(id=1, username="alice123")

#     headers = {"token": "anything"}
#     files = {"file": ("test_note.wav", in_memory_audio, "audio/wav")}
#     response = client_with_data.post("/upload_audio/", files=files, headers=headers)

#     assert response.status_code == 200
#     data = response.json()
#     assert "health" in " ".join(data["tags"]).lower()
#     assert "travel" in " ".join(data["tags"]).lower()

#     # Clean up auth override
#     app.dependency_overrides.pop(get_current_user, None)
