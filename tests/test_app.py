from sqlalchemy import select
from utils import load_hierarchy, normalize, add_tags
from models import Tag, Note, note_tags, tag_parents


def test_add_tags_creates_tags(db):
    hierarchy_data = load_hierarchy("tests/test_hierarchy.json")

    add_tags(hierarchy_data, db=db)
    db.commit()

    # get all tag names from DB
    names = {t.name for t in db.query(Tag).all()}

    # expected set of normalized tags
    expected_names = {
        "languages",
        "english",
        "spanish",
        "health",
        "doctors",
        "cardiologist",
        "dermatologist",
        "nutrition",
        "diet",
        "supplements",
        "pets",
        "dogs",
        "cats",
        "fitness",
        "workout",
        "yoga",
        "travel",
        "food",
        "restaurants",
        "cafes",
        "travel_insurance",
        "breathing_exercises",
        "wellness",
        "meditation",
        "mindfulness",
        "others",
    }

    assert names == expected_names


def test_tag_parent_child_relationships(db):
    hierarchy_data = load_hierarchy("tests/test_hierarchy.json")
    add_tags(hierarchy_data, db=db)
    db.commit()

    doctors = db.query(Tag).filter_by(name="doctors").one()
    health = db.query(Tag).filter_by(name="health").one()
    fitness = db.query(Tag).filter_by(name="fitness").one()

    assert doctors.parents == [health]
    assert doctors in health.children
    assert fitness.parents == []


def test_note_creation(db):
    note = Note(content="test entry", media_type="text")
    db.add(note)
    db.commit()

    assert db.query(Note).count() == 1


def test_note_tag_association(db):
    hierarchy_data = load_hierarchy("tests/test_hierarchy.json")
    add_tags(hierarchy_data, db=db)
    db.commit()

    note = Note(content="test", media_type="text")

    for name in ["health", "diet", "fitness", "doctors"]:
        tag = db.query(Tag).filter_by(name=normalize(name)).one()
        note.tags.append(tag)

    db.add(note)
    db.commit()
    db.refresh(note)

    assert len(note.tags) == 4

    rows = db.execute(select(note_tags).where(note_tags.c.note_id == note.id)).all()

    assert len(rows) == 4


def test_note_creates_missing_tag(db):

    missing_tag_name = "NewTag"
    assert db.query(Tag).filter_by(name=normalize(missing_tag_name)).first() is None

    note = Note(content="Test note with new tag", media_type="text")

    # Attach the tag: if add_tags logic is used in your app, you might call that here
    # For this test, we'll mimic auto-create behavior
    tag = db.query(Tag).filter_by(name=normalize(missing_tag_name)).first()
    if tag is None:
        tag = Tag(name=normalize(missing_tag_name))
        db.add(tag)
        db.commit()
        db.refresh(tag)

    note.tags.append(tag)
    db.add(note)
    db.commit()
    db.refresh(note)

    # Assertions
    # 1️⃣ Note has the tag
    assert len(note.tags) == 1
    assert note.tags[0].name == normalize(missing_tag_name)

    # 2️⃣ Tag exists in DB
    tag_in_db = db.query(Tag).filter_by(name=normalize(missing_tag_name)).one_or_none()
    assert tag_in_db is not None
    assert tag_in_db.name == normalize(missing_tag_name)

    # 3️⃣ Association table has a row
    # row_count = db.execute(select("note_tags")).fetchall()
    rows = db.execute(select(note_tags).where(note_tags.c.note_id == note.id)).all()
    assert len(rows) == 1


def test_full_note_flow(db):
    hierarchy_data = load_hierarchy("tests/test_hierarchy.json")

    # seed hierarchy
    add_tags(hierarchy_data, db=db)
    db.commit()

    # create note
    content = "test entry"
    media_type = "text"
    tags = ["health", "diet", "fitness", "doctors"]

    note = Note(content=content, media_type=media_type)

    for name in tags:
        tag = db.query(Tag).filter_by(name=normalize(name)).first()
        assert tag is not None
        note.tags.append(tag)

    db.add(note)
    db.commit()
    db.refresh(note)

    # ---------- ASSERTIONS ----------

    # only one note
    assert db.query(Note).count() == 1

    # THIS note has exactly 4 tags
    assert len(note.tags) == 4
    tag_names = {t.name for t in note.tags}

    # association rows ONLY for this note
    rows = db.execute(select(note_tags).where(note_tags.c.note_id == note.id)).all()
    assert len(rows) == 4

    # ---- hierarchy assertions ----
    doctors = db.query(Tag).filter_by(name="doctors").one()
    health = db.query(Tag).filter_by(name="health").one()
    fitness = db.query(Tag).filter_by(name="fitness").one()

    # doctors -> health
    assert doctors.parents == [health]
    assert doctors in health.children

    # fitness has no parents
    assert fitness.parents == []


def test_create_note_text(client):
    response = client.post("/notes/", data={"content": "hello", "tags": "health"})
    assert response.status_code == 200
    assert "id" in response.json()


def test_create_note_with_new_tag(db, client):
    # --- Ensure "others" exists ---
    others_tag = db.query(Tag).filter_by(name="others").first()
    if not others_tag:
        others_tag = Tag(name="others")
        db.add(others_tag)
        db.commit()
        db.refresh(others_tag)

    # --- Send POST request to create note ---
    response = client.post(
        "/notes/",
        data={"content": "Test note", "tags": "newtag"},
    )

    assert response.status_code == 200
    data = response.json()
    note_id = data["id"]

    # --- Check note in DB ---
    note = db.query(Note).filter_by(id=note_id).first()
    assert note is not None
    assert note.content == "Test note"

    # --- Check tag auto-created ---
    tag = db.query(Tag).filter_by(name="newtag").first()
    assert tag is not None
    assert tag.name == "newtag"

    # --- Check parent is "others" ---
    parents = [p.name for p in tag.parents]
    assert "others" in parents

    # --- Check note-tag association ---
    assert tag in note.tags

    # --- Optional: cleanup ---
    db.delete(note)
    db.delete(tag)
    db.commit()


def test_create_note_without_content_or_file(client):
    response = client.post(
        "/notes/",
        data={"content": "", "tags": "health"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Note must contain text or an image."
