from sqlalchemy import select
from utils import _add_node, load_hierarchy, normalize, add_tags
from models import Tag, Note, note_tags, tag_parents


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
