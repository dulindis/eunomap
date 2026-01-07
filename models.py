import re
from sqlalchemy import (
    Column,
    Boolean,
    DateTime,
    Integer,
    String,
    ForeignKey,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship, validates
from datetime import datetime, timezone

# from db import Base
from base import Base


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

    created_at = Column(DateTime, default=datetime.utcnow)

    owner_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )

    # Relationship: One Note can have Many Tags
    tags = relationship(
        "Tag",
        secondary=note_tags,
        back_populates="notes",
        passive_deletes=True,
    )

    owner = relationship("User", back_populates="notes")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)

    # Human-readable label (NOT unique)
    label = Column(String, index=True, nullable=False)  # i.e  e.g. "mental_health"
    key = Column(String, nullable=False)  # same as label; stable

    # Materialized path, e.g. "/pets/health"
    path = Column(
        String, index=True, nullable=False
    )  # path: composed of slug segments, e.g. "/health/mental-health"

    # Tree structure
    parent_id = Column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=True
    )
    # Relationships
    parent = relationship(
        "Tag",
        remote_side=[id],
        backref="children",
    )

    notes = relationship(
        "Note",
        secondary="note_tags",
        back_populates="tags",
    )

    __table_args__ = (
        # Enforce uniqueness only among siblings
        # (same parent cannot have two "Health")
        UniqueConstraint(
            "parent_id", "key", name="uq_tag_sibling_key"
        ),  # This guarantees your hierarchy cannot become inconsistent.
        {},
    )


class TagUsage(Base):
    __tablename__ = "tag_usage"

    id = Column(Integer, primary_key=True)
    tag_id = Column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # When this tag was used (e.g. note created / tag added)
    used_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    tag = relationship("Tag", backref="usage_events")


class TagStats(Base):
    __tablename__ = "tag_stats"

    tag_id = Column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )

    # All-time count
    total_count = Column(Integer, nullable=False, default=0)

    # Recent window counts (tune to your needs)
    last_24h_count = Column(Integer, nullable=False, default=0)
    last_7d_count = Column(Integer, nullable=False, default=0)

    # Last time this tag was used
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    tag = relationship("Tag", backref="stats")


# When a note is created or a tag is attached to a note:

# Insert into note_tags (your join table).

# Insert one row into tag_usage per tag.


# Later you can aggregate counts per time bucket in SQL (e.g. “last 24h”).
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(
        String, unique=True, index=True, nullable=False
    )  # GitHub username
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=True)  # None if OAuth user
    is_active = Column(Boolean, default=True)
    # created_at = Column(String, default=datetime.fromtimestamp())
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    notes = relationship("Note", back_populates="owner")

    @validates("email")
    def validate_email(self, key, value):
        if value:
            if not re.match(r"[^@]+@[^@]+\.[^@]+", value):
                raise ValueError(f"Invalid email address: {value}")
        return value

    @validates("username")
    def validate_username(self, key, value):
        if not value or len(value) < 3:
            raise ValueError("Username must be at least 3 characters long")
        return value
