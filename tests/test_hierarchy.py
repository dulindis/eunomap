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


# def test_full_note_flow(db):
#     hierarchy_data = load_hierarchy("tests/test_hierarchy.json")

#     # seed hierarchy
#     add_tags(hierarchy_data, db=db)
#     db.commit()

#     # create note
#     content = "test entry"
#     media_type = "text"
#     tags = ["health", "diet", "fitness", "doctors"]

#     note = Note(content=content, media_type=media_type)

#     for name in tags:
#         tag = db.query(Tag).filter_by(name=normalize(name)).first()
#         assert tag is not None
#         note.tags.append(tag)

#     db.add(note)
#     db.commit()
#     db.refresh(note)

#     # ---------- ASSERTIONS ----------

#     # only one note
#     assert db.query(Note).count() == 1

#     # THIS note has exactly 4 tags
#     assert len(note.tags) == 4
#     tag_names = {t.name for t in note.tags}

#     # association rows ONLY for this note
#     rows = db.execute(select(note_tags).where(note_tags.c.note_id == note.id)).all()
#     assert len(rows) == 4

#     # ---- hierarchy assertions ----
#     doctors = db.query(Tag).filter_by(name="doctors").one()
#     health = db.query(Tag).filter_by(name="health").one()
#     fitness = db.query(Tag).filter_by(name="fitness").one()

#     # doctors -> health
#     assert doctors.parents == [health]
#     assert doctors in health.children

#     # fitness has no parents
#     assert fitness.parents == []
