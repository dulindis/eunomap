from pathlib import Path
from sqlalchemy import select
from utils import load_hierarchy, normalize, add_tags
from models import Tag, Note
from models import note_tags, tag_parents
from tests import test_database
import pytest


@pytest.fixture()
def session():  # <-- fixture is NOT named db
    db = test_database.SessionLocal()
    yield db
    db.rollback()
    db.close()


def test_hierarchy_and_note_creation(session):
    hierarchy_data = {
        "Health": {
            "Nutrition": ["Diet"],
            "Doctors": ["Cardiologist"],
        },
        "Fitness": ["Health"],  # Health is child here
    }

    # seed hierarchy
    add_tags(hierarchy_data, db=session)
    session.commit()

    # create note
    note = Note(content="test entry", media_type="text")

    for name in ["health", "diet", "fitness", "doctors"]:
        tag = db.query(Tag).filter_by(name=normalize(name)).first()
        assert tag is not None
        note.tags.append(tag)

    db.add(note)
    db.commit()

    # ---------- ASSERTIONS ----------

    assert db.query(Note).count() == 1
    assert db.query(Tag).count() >= 4

    # note_tags association
    rows = db.execute(select(note_tags)).all()
    assert len(rows) == 4

    # hierarchy relations
    parent_rows = db.execute(select(tag_parents)).all()
    assert len(parent_rows) > 0
    # ---------- Main test ----------
    # def test_hierarchy_and_note_creation():
    db = db.SessionLocal()

    hierarchy_data = {
        "Health": {
            "Nutrition": ["Diet"],
            "Doctors": ["Cardiologist"],
        },
        "Fitness": ["Health"],  # Health is child here
    }

    # seed hierarchy
    add_tags(hierarchy_data, db=db)
    db.commit()

    # create note
    note = Note(content="test entry", media_type="text")
    for name in ["health", "diet", "fitness", "doctors"]:
        tag = db.query(Tag).filter_by(name=normalize(name)).first()
        assert tag is not None
        note.tags.append(tag)

    db.add(note)
    db.commit()

    # ---------- ASSERTIONS ----------
    assert db.query(Note).count() == 1
    assert db.query(Tag).count() >= 4

    # note_tags association
    rows = db.execute(select(note_tags)).all()
    assert len(rows) == 4

    # hierarchy relations
    parent_rows = db.execute(select(tag_parents)).all()
    assert len(parent_rows) > 0


# if __name__ == "__main__":

#     # Load and seed hierarchy
#     hierarchy_path = Path("hierarchy.json")
#     if not hierarchy_path.exists():
#         # minimal example hierarchy if file doesn't exist
#         hierarchy_data = {
#             "Health": {
#                 "Nutrition": ["Diet", "Healthy Eating"],
#                 "Doctors": ["Cardiologist", "Dermatologist"],
#             },
#             "Fitness": ["Workout", "Yoga"],
#         }
#     else:
#         hierarchy_data = load_hierarchy("hierarchy.json")

#     add_tags(hierarchy_data, db=db)
#     db.commit()

#     # Add test note
#     note = Note(content="test entry", media_type="text")
#     tag_names = ["health", "diet", "fitness", "doctors"]
#     for name in tag_names:
#         tag = db.query(Tag).filter_by(name=normalize(name)).first()
#         if tag:
#             note.tags.append(tag)
#     db.add(note)
#     db.commit()

#     # ---------- Print results ----------
#     print("\n--- Notes ---")
#     for n in db.query(Note).all():
#         print(n.id, n.content, [t.name for t in n.tags])

#     print("\n--- Tags ---")
#     for t in db.query(Tag).all():
#         print(
#             t.id,
#             t.name,
#             "Parents:",
#             [p.name for p in t.parents],
#             "Children:",
#             [c.name for c in t.children],
#         )

#     print("\n--- note_tags table ---")
#     result = db.execute(select(note_tags)).all()
#     for row in result:
#         print(dict(row._mapping))

#     print("\n--- tag_parents table ---")
#     result = db.execute(select(tag_parents)).all()
#     for row in result:
#         print(dict(row._mapping))
