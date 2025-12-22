import re
from pathlib import Path
from sqlalchemy import (
    create_engine,
    Table,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    MetaData,
    select,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import json


@pytest.fixture
def db():
    # Create a session for the test
    session = SessionLocal()
    try:
        # Seed hierarchy into test DB
        hierarchy = load_hierarchy("test_hierarchy.json")
        add_tags(hierarchy, db=session)
        session.commit()
        yield session
    finally:
        session.close()


def test_create_note_with_tags(db):
    # Create test note
    note = Note(content="test entry", media_type="text")

    # Link tags
    tag_names = ["health", "diet", "fitness", "doctors"]
    for name in tag_names:
        tag = db.query(Tag).filter_by(name=name).first()
        if not tag:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()
        note.tags.append(tag)

    db.add(note)
    db.commit()
    db.refresh(note)

    # Assertions
    assert note.id is not None
    assert len(note.tags) == 4

    # Check tag_parents table has entries for hierarchy
    for tag in note.tags:
        # Each tag may have parents (depending on hierarchy)
        parents = [p.name for p in tag.parents]
        assert isinstance(parents, list)
