"""
Tests for tag mode resolution and markdown utilities.

These tests verify:
1. Tag resolution with disambiguation
2. Both path and flat tag modes
3. Markdown import/export with different modes
4. LLM export format
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup test database
TEST_DATABASE_URL = "sqlite:///./test_tag_modes.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_test_db():
    """Get a test database session."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test."""
    from base import Base
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_tags(db_session):
    """Create sample tags for testing."""
    from models import Tag
    from utils.tag_utils import get_or_create_tag_by_path
    
    # Create hierarchical tags (path mode)
    health = get_or_create_tag_by_path(db_session, "health")
    kids = get_or_create_tag_by_path(db_session, "kids")
    work = get_or_create_tag_by_path(db_session, "work")
    
    # Create child tags
    health_doctors = get_or_create_tag_by_path(db_session, "health/doctors")
    kids_doctors = get_or_create_tag_by_path(db_session, "kids/doctors")
    work_doctors = get_or_create_tag_by_path(db_session, "work/doctors")
    
    db_session.commit()
    
    return {
        "health": health,
        "kids": kids,
        "work": work,
        "health_doctors": health_doctors,
        "kids_doctors": kids_doctors,
        "work_doctors": work_doctors,
    }


# =============================================================================
# Tag Mode Configuration Tests
# =============================================================================

def test_tag_mode_config_defaults():
    """Test default tag mode configuration."""
    from utils.tag_modes import TagModeConfig, TagMode
    
    config = TagModeConfig()
    
    assert config.mode == TagMode.PATH
    assert config.disambiguation_enabled is True
    assert config.auto_create_tags is True


def test_tag_mode_config_path_mode():
    """Test path mode configuration."""
    from utils.tag_modes import TagModeConfig, TagMode
    
    config = TagModeConfig(mode=TagMode.PATH)
    
    assert config.mode == TagMode.PATH


def test_tag_mode_config_flat_mode():
    """Test flat mode configuration."""
    from utils.tag_modes import TagModeConfig, TagMode
    
    config = TagModeConfig(mode=TagMode.FLAT)
    
    assert config.mode == TagMode.FLAT


# =============================================================================
# Tag Resolution Tests - Path Mode
# =============================================================================

def test_resolve_unique_match_path_mode(db_session, sample_tags):
    """Test resolving a unique tag match in path mode."""
    from utils.tag_modes import resolve_tag_for_mode, TagMode, set_tag_mode_config, TagModeConfig
    
    # Set path mode
    set_tag_mode_config(TagModeConfig(mode=TagMode.PATH))
    
    # Resolve an exact path
    result = resolve_tag_for_mode("health/doctors", db_session, TagMode.PATH)
    
    assert result.status == "unique_match"
    assert result.selected_tag is not None
    assert result.selected_tag.path == "/health/doctors"


def test_resolve_multiple_matches_path_mode(db_session, sample_tags):
    """Test resolving a tag with multiple matches (disambiguation needed)."""
    from utils.tag_modes import resolve_tag_for_mode, TagMode, set_tag_mode_config, TagModeConfig
    
    set_tag_mode_config(TagModeConfig(mode=TagMode.PATH))
    
    # Resolve "doctors" - should find multiple matches
    result = resolve_tag_for_mode("doctors", db_session, TagMode.PATH)
    
    assert result.status == "multiple_matches"
    assert len(result.candidates) == 3  # health/doctors, kids/doctors, work/doctors
    assert result.can_create is True


def test_resolve_not_found_path_mode(db_session, sample_tags):
    """Test resolving a non-existent tag."""
    from utils.tag_modes import resolve_tag_for_mode, TagMode, set_tag_mode_config, TagModeConfig
    
    set_tag_mode_config(TagModeConfig(mode=TagMode.PATH))
    
    result = resolve_tag_for_mode("nonexistent", db_session, TagMode.PATH)
    
    assert result.status == "not_found"
    assert result.can_create is True
    # Should suggest parent categories
    assert len(result.suggested_parents) > 0


# =============================================================================
# Tag Resolution Tests - Flat Mode
# =============================================================================

def test_resolve_unique_match_flat_mode(db_session):
    """Test resolving a unique tag in flat mode."""
    from models import Tag
    from utils.tag_modes import resolve_tag_for_mode, TagMode, set_tag_mode_config, TagModeConfig
    
    set_tag_mode_config(TagModeConfig(mode=TagMode.FLAT))
    
    # Create a flat tag
    tag = Tag(label="doctors", key="doctors", path="/doctors")
    db_session.add(tag)
    db_session.commit()
    
    result = resolve_tag_for_mode("doctors", db_session, TagMode.FLAT)
    
    assert result.status == "unique_match"
    assert result.selected_tag is not None
    assert result.selected_tag.label == "doctors"


def test_resolve_not_found_flat_mode(db_session):
    """Test resolving non-existent tag in flat mode."""
    from utils.tag_modes import resolve_tag_for_mode, TagMode, set_tag_mode_config, TagModeConfig
    
    set_tag_mode_config(TagModeConfig(mode=TagMode.FLAT))
    
    result = resolve_tag_for_mode("unknown", db_session, TagMode.FLAT)
    
    assert result.status == "not_found"
    assert result.can_create is True


# =============================================================================
# Markdown Export/Import Tests
# =============================================================================

def test_markdown_export_path_mode(db_session):
    """Test markdown export with path mode tags."""
    from models import Note, Tag
    from schemas import NoteOut
    from utils.markdown_utils import note_to_markdown
    from utils.tag_modes import TagMode
    
    # Create note with path tags
    note = Note(title="Test Note", content="Test content")
    tag1 = Tag(label="doctors", key="doctors", path="/health/doctors")
    tag2 = Tag(label="health", key="health", path="/health")
    
    db_session.add_all([note, tag1, tag2])
    note.tags.append(tag1)
    note.tags.append(tag2)
    db_session.commit()
    
    # Export to markdown
    note_out = NoteOut.model_validate(note)
    md = note_to_markdown(note_out, tag_mode=TagMode.PATH)
    
    assert "tag_mode: path" in md
    assert "/health/doctors" in md
    assert "/health" in md


def test_markdown_export_flat_mode(db_session):
    """Test markdown export with flat mode tags."""
    from models import Note, Tag
    from schemas import NoteOut
    from utils.markdown_utils import note_to_markdown
    from utils.tag_modes import TagMode
    
    # Create note with flat tags
    note = Note(title="Test Note", content="Test content")
    tag1 = Tag(label="doctors", key="doctors", path="/doctors")
    tag2 = Tag(label="pediatrics", key="pediatrics", path="/pediatrics")
    
    db_session.add_all([note, tag1, tag2])
    note.tags.append(tag1)
    note.tags.append(tag2)
    db_session.commit()
    
    # Export to markdown
    note_out = NoteOut.model_validate(note)
    md = note_to_markdown(note_out, tag_mode=TagMode.FLAT)
    
    assert "tag_mode: flat" in md
    assert "doctors" in md
    assert "pediatrics" in md


def test_markdown_import_path_mode(db_session):
    """Test markdown import with path mode."""
    from utils.markdown_utils import markdown_to_parsed_note, import_markdown_note
    
    md = """---
id: 1
title: Test Note
tag_mode: "path"
tags:
  - "health/doctors"
  - "kids/doctors"
---

# Test Content
"""
    # Parse the markdown
    parsed = markdown_to_parsed_note(md)
    
    assert parsed.title == "Test Note"
    assert "health/doctors" in parsed.tag_paths
    assert "kids/doctors" in parsed.tag_paths


def test_markdown_import_flat_mode(db_session):
    """Test markdown import with flat mode."""
    from utils.markdown_utils import markdown_to_parsed_note
    
    md = """---
id: 2
title: Flat Note
tag_mode: "flat"
tags:
  - "doctors"
  - "pediatrics"
---

# Flat Content
"""
    parsed = markdown_to_parsed_note(md)
    
    assert parsed.title == "Flat Note"
    assert "doctors" in parsed.tags
    assert "pediatrics" in parsed.tags


# =============================================================================
# Strategy Tests
# =============================================================================

def test_path_strategy_export(db_session):
    """Test path strategy export."""
    from models import Note, Tag
    from schemas import NoteOut
    from utils.tag_modes import get_tag_strategy, TagMode
    
    note = Note(title="Test", content="Content")
    tag = Tag(label="doctors", key="doctors", path="/health/doctors")
    
    db_session.add_all([note, tag])
    note.tags.append(tag)
    db_session.commit()
    
    strategy = get_tag_strategy(TagMode.PATH)
    exported = strategy.export_tags(note)
    
    assert "/health/doctors" in exported


def test_flat_strategy_export(db_session):
    """Test flat strategy export."""
    from models import Note, Tag
    from utils.tag_modes import get_tag_strategy, TagMode
    
    note = Note(title="Test", content="Content")
    tag = Tag(label="doctors", key="doctors", path="/doctors")
    
    db_session.add_all([note, tag])
    note.tags.append(tag)
    db_session.commit()
    
    strategy = get_tag_strategy(TagMode.FLAT)
    exported = strategy.export_tags(note)
    
    assert "doctors" in exported


# =============================================================================
# LLM Export Tests
# =============================================================================

def test_llm_export_format(db_session):
    """Test LLM export format contains expected fields."""
    from models import Note, Tag
    from utils.llm_utils import export_all_for_llm
    
    # Create test data
    note = Note(title="Test Note", content="Test content about doctors")
    tag = Tag(label="doctors", key="doctors", path="/health/doctors")
    
    db_session.add_all([note, tag])
    note.tags.append(tag)
    db_session.commit()
    
    # Export for LLM
    data = export_all_for_llm(db_session)
    
    assert data.mode in ["path", "flat"]
    assert len(data.tags) > 0
    assert len(data.notes) > 0
    assert "total_notes" in data.statistics
    assert "total_tags" in data.statistics


def test_llm_export_tags_have_required_fields(db_session):
    """Test LLM export tags have all required fields."""
    from models import Tag
    from utils.llm_utils import export_tags_for_llm
    
    tag = Tag(label="doctors", key="doctors", path="/health/doctors")
    db_session.add(tag)
    db_session.commit()
    
    exports = export_tags_for_llm(db_session)
    
    assert len(exports) == 1
    assert exports[0].label == "doctors"
    assert exports[0].path == "/health/doctors"
    assert exports[0].id == tag.id


# =============================================================================
# Query Tests
# =============================================================================

def test_query_notes_by_subtree(db_session):
    """Test querying notes by tag subtree."""
    from models import Note, Tag
    from utils.llm_utils import query_notes_by_tag_path_prefix
    
    # Create notes with different tags
    note1 = Note(content="Health content")
    note2 = Note(content="Kids content")
    
    tag1 = Tag(label="doctors", key="doctors", path="/health/doctors")
    tag2 = Tag(label="doctors", key="doctors", path="/kids/doctors")
    
    db_session.add_all([note1, note2, tag1, tag2])
    note1.tags.append(tag1)
    note2.tags.append(tag2)
    db_session.commit()
    
    # Query health subtree
    notes = query_notes_by_tag_path_prefix(db_session, "health")
    
    assert len(notes) == 1
    assert notes[0].content == "Health content"


def test_get_tag_hierarchy_tree(db_session):
    """Test getting tag hierarchy as tree."""
    from models import Tag
    from utils.llm_utils import get_tag_hierarchy_tree
    from utils.tag_utils import get_or_create_tag_by_path
    
    get_or_create_tag_by_path(db_session, "health/doctors")
    get_or_create_tag_by_path(db_session, "health/fitness")
    get_or_create_tag_by_path(db_session, "work")
    db_session.commit()
    
    tree = get_tag_hierarchy_tree(db_session)
    
    assert "health" in tree
    assert "doctors" in tree["health"]
    assert "fitness" in tree["health"]
    assert "work" in tree


# =============================================================================
# Integration Tests
# =============================================================================

def test_tag_resolution_flow_multiple_matches(db_session, sample_tags):
    """Test complete tag resolution flow with multiple matches."""
    from utils.tag_modes import resolve_tag_for_mode, TagMode, set_tag_mode_config, TagModeConfig
    from utils.tag_modes import get_or_create_tag as strategy_get_or_create
    
    set_tag_mode_config(TagModeConfig(
        mode=TagMode.PATH,
        disambiguation_enabled=True,
        auto_create_tags=True,
    ))
    
    # Step 1: User types "doctors" - should get multiple matches
    result = resolve_tag_for_mode("doctors", db_session, TagMode.PATH)
    
    assert result.status == "multiple_matches"
    assert len(result.candidates) == 3
    
    # Step 2: Frontend shows dialog, user selects "health/doctors"
    selected = result.candidates[0]  # health/doctors
    
    # Step 3: Attach selected tag to note
    from models import Note
    note = Note(content="Found a good doctor")
    db_session.add(note)
    db_session.commit()
    
    # Find the tag by path
    tag = db_session.query(Tag).filter(Tag.path == selected.path).first()
    note.tags.append(tag)
    db_session.commit()
    
    assert len(note.tags) == 1
    assert note.tags[0].path == "/health/doctors"


def test_disable_disambiguation_flow(db_session):
    """Test disabling disambiguation - auto-creates or uses flat tags."""
    from utils.tag_modes import resolve_tag_for_mode, TagMode, set_tag_mode_config, TagModeConfig
    
    # Set flat mode with disambiguation disabled
    set_tag_mode_config(TagModeConfig(
        mode=TagMode.FLAT,
        disambiguation_enabled=False,  # Disable disambiguation
        auto_create_tags=True,
    ))
    
    # In flat mode without disambiguation, "doctors" would either:
    # 1. Find existing tag, or
    # 2. Auto-create new tag (if enabled)
    
    result = resolve_tag_for_mode("doctors", db_session, TagMode.FLAT)
    
    # Should either be unique_match or not_found with can_create
    assert result.status in ["unique_match", "not_found"]
    assert result.can_create is True
