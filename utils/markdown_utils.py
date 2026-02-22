"""
Markdown Import/Export Utilities with YAML Front Matter

Supports both tag modes:
- Mode A (path): Hierarchical paths like "health/doctors"
- Mode B (flat): Flat tags like "doctors"

The export format explicitly declares the tag mode in front matter.
"""

import re
import yaml
from datetime import datetime
from typing import Optional

from models import Note, Tag
from schemas import NoteOut, ParsedNote
from utils.tag_modes import (
    TagMode,
    get_tag_mode_config,
    get_tag_strategy,
    get_current_strategy,
)


# =============================================================================
# YAML Front Matter Design
# =============================================================================

def note_to_markdown(
    note: NoteOut,
    tag_mode: Optional[TagMode] = None,
    include_metadata: bool = True,
) -> str:
    """
    Converts a NoteOut object into a Markdown string with YAML front matter.
    
    Args:
        note: Note to convert
        tag_mode: Override tag mode (defaults to config)
        include_metadata: Whether to include YAML front matter
        
    Returns:
        Markdown string with YAML front matter
    """
    if tag_mode is None:
        tag_mode = get_tag_mode_config().mode
    
    strategy = get_tag_strategy(tag_mode)
    
    # Export tags based on current mode
    tags = strategy.export_tags(note)
    
    # Build metadata
    created_str = note.created_at.isoformat() if note.created_at else None
    updated_str = note.updated_at.isoformat() if note.updated_at else None
    
    meta = {
        "id": note.id,
        "title": note.title,
        "created_at": created_str,
        "updated_at": updated_str,
        "tag_mode": tag_mode.value,  # Explicitly declare mode
        "tags": tags,
    }
    
    if note.media_path or note.media_type:
        meta["media"] = {
            "path": note.media_path,
            "type": note.media_type,
        }
    
    # Clean up empty values
    meta = {k: v for k, v in meta.items() if v}
    
    # Build output
    if include_metadata:
        front = "---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n\n"
    else:
        front = ""
    
    content = note.content or ""
    return front + content


def note_to_markdown_path_mode(note: NoteOut) -> str:
    """Export note with path-based tags (Mode A)."""
    return note_to_markdown(note, tag_mode=TagMode.PATH)


def note_to_markdown_flat_mode(note: NoteOut) -> str:
    """Export note with flat tags (Mode B)."""
    return note_to_markdown(note, tag_mode=TagMode.FLAT)


def markdown_to_parsed_note(md: str) -> ParsedNote:
    """
    Parses a Markdown string with YAML front matter into a ParsedNote model.
    
    Detects tag_mode from front matter and handles accordingly.
    """
    # Regex to extract YAML front matter enclosed in ---
    match = re.match(r"^---\n(.*?)\n---\n+", md, re.DOTALL)
    
    if not match:
        # No front matter - treat entire string as content
        return ParsedNote(content=md.strip())
    
    yaml_block = match.group(1)
    content = md[match.end():].strip()
    
    try:
        meta = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError:
        meta = {}
    
    # Extract tag_mode from front matter
    tag_mode_str = meta.get("tag_mode", "path")
    tag_mode = TagMode.PATH if tag_mode_str == "path" else TagMode.FLAT
    
    # Get tags based on mode
    # For backward compatibility, also check old field names
    tags = meta.get("tags", [])
    tag_paths = meta.get("tag_paths", [])
    
    # Handle legacy format (both tags and tag_paths in same file)
    if tag_paths and not tags:
        if tag_mode == TagMode.PATH:
            tags = tag_paths
        else:
            # In flat mode, use tags as-is
            pass
    
    media = meta.get("media", {})
    
    # Convert timestamps
    created_at = None
    if meta.get("created_at"):
        try:
            created_at = datetime.fromisoformat(meta["created_at"])
        except ValueError:
            pass
    
    updated_at = None
    if meta.get("updated_at"):
        try:
            updated_at = datetime.fromisoformat(meta["updated_at"])
        except ValueError:
            pass
    
    return ParsedNote(
        id=meta.get("id"),
        title=meta.get("title"),
        author=meta.get("author"),
        created_at=created_at,
        updated_at=updated_at,
        tags=tags if tag_mode == TagMode.FLAT else [],
        tag_paths=tags if tag_mode == TagMode.PATH else [],
        media_path=media.get("path"),
        media_type=media.get("type"),
        content=content,
    )


def import_markdown_note(
    db,
    md: str,
    owner_id: Optional[int] = None,
    tag_mode: Optional[TagMode] = None,
) -> Note:
    """
    Import a Markdown note into the database.
    
    Args:
        db: Database session
        md: Markdown content with YAML front matter
        owner_id: Optional owner user ID
        tag_mode: Override tag mode (defaults to detected or config)
        
    Returns:
        Created Note object
    """
    parsed = markdown_to_parsed_note(md)
    
    # Determine tag mode
    if tag_mode is None:
        # Try to detect from parsed note
        if parsed.tag_paths:
            tag_mode = TagMode.PATH
        elif parsed.tags:
            tag_mode = TagMode.FLAT
        else:
            tag_mode = get_tag_mode_config().mode
    
    strategy = get_tag_strategy(tag_mode)
    
    # Create note
    note = Note(
        title=parsed.title,
        content=parsed.content,
        media_path=parsed.media_path,
        media_type=parsed.media_type or "text",
        created_at=parsed.created_at,
        updated_at=parsed.updated_at,
        owner_id=owner_id,
    )
    
    # Resolve and attach tags
    tag_strings = parsed.tag_paths if tag_mode == TagMode.PATH else parsed.tags
    if tag_strings:
        resolved_tags = strategy.import_tags(db, tag_strings)
        for tag in resolved_tags:
            if tag not in note.tags:
                note.tags.append(tag)
    
    db.add(note)
    db.commit()
    db.refresh(note)
    
    return note


# =============================================================================
# Example Output Formats
# =============================================================================

# Example Mode A (path) output:
EXAMPLE_PATH_MODE = '''---
id: 1
title: Finding a Doctor
created_at: 2024-01-15T10:30:00
updated_at: 2024-01-15T10:30:00
tag_mode: "path"
tags:
  - "health/doctors"
  - "kids/doctors"
---

# Finding a Doctor

Here are some tips for finding a good doctor for your kids...
'''

# Example Mode B (flat) output:
EXAMPLE_FLAT_MODE = '''---
id: 2
title: Finding a Doctor
created_at: 2024-01-15T10:30:00
updated_at: 2024-01-15T10:30:00
tag_mode: "flat"
tags:
  - "doctors"
  - "pediatrics"
---

# Finding a Doctor

Here are some tips for finding a good doctor...
'''


def get_example_markdown(mode: TagMode = TagMode.PATH) -> str:
    """Get example markdown for the specified mode."""
    if mode == TagMode.PATH:
        return EXAMPLE_PATH_MODE
    return EXAMPLE_FLAT_MODE
