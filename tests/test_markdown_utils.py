import pytest
import datetime
from schemas import NoteOut, TagOut
from utils.markdown_utils import note_to_markdown, markdown_to_parsed_note

def test_markdown_roundtrip():
    # 1. Create a mock NoteOut with both title and timestamps
    dt = datetime.datetime(2026, 2, 22, 10, 0, 0, tzinfo=datetime.timezone.utc)
    
    tag1 = TagOut(id=1, label="doctors", path="health/doctors")
    tag2 = TagOut(id=2, label="dogs", path="pets/dogs")

    note = NoteOut(
        id=42,
        title="My Visit",
        content="The quick brown fox jumps over the lazy dog.",
        media_path="static/image.png",
        media_type="image",
        created_at=dt,
        updated_at=dt,
        tags=[tag1, tag2]
    )

    # 2. Convert to Markdown
    md_string = note_to_markdown(note)

    # 3. Assert on output syntax
    assert "title: My Visit" in md_string
    assert "health/doctors" in md_string
    assert "dogs" in md_string
    assert "The quick brown fox" in md_string

    # 4. Parse back into a ParsedNote
    parsed = markdown_to_parsed_note(md_string)

    assert parsed.id == 42
    assert parsed.title == "My Visit"
    assert parsed.content == "The quick brown fox jumps over the lazy dog."
    assert "doctors" in parsed.tags
    assert "dogs" in parsed.tags
    assert "health/doctors" in parsed.tag_paths
    assert "pets/dogs" in parsed.tag_paths
    assert parsed.media_path == "static/image.png"
    assert parsed.media_type == "image"
    assert parsed.created_at == dt
    assert parsed.updated_at == dt
