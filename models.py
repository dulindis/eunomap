from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

# Association Table (The bridge between Notes and Tags)
note_tags = Table(
    "note_tags",
    Base.metadata,
    Column("note_id", Integer, ForeignKey("notes.id", ondelete="CASCADE")),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE")),
)


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=True)  # The text note
    media_path = Column(String, nullable=True)  # "static/uploads/image.png"
    media_type = Column(String, default="text")  # text, image, pdf
    created_at = Column(DateTime, default=datetime.utcnow())

    # Relationship: One Note can have Many Tags
    tags = relationship(
        "Tag",
        secondary=note_tags,
        back_populates="notes",
        passive_deletes=True,
    )


tag_parents = Table(
    "tag_parents",
    Base.metadata,
    Column("child_id", Integer, ForeignKey("tags.id", ondelete="CASCADE")),
    Column("parent_id", Integer, ForeignKey("tags.id", ondelete="CASCADE")),
)


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    # parent_id = Column(Integer, ForeignKey("tags.id"), nullable=True)

    # Self-referential relationships
    # parent = relationship("Tag", remote_side=[id], backref="children")
    parents = relationship(
        "Tag",
        secondary=tag_parents,
        primaryjoin=id == tag_parents.c.child_id,
        secondaryjoin=id == tag_parents.c.parent_id,
        backref="children",
    )
    notes = relationship("Note", secondary=note_tags, back_populates="tags")
