"""
LLM-Assisted Hierarchy Generation Utilities

This module provides data shapes and hooks for:
1. Exporting notes and tags in a compact format for LLM analysis
2. Importing LLM-produced hierarchy mappings (new paths, merges, renames)

No actual LLM is wired in - these are data transformation utilities
that can be used with any LLM API or local model.
"""

from dataclasses import dataclass, field
from typing import Any
from sqlalchemy.orm import Session

from models import Note, Tag
from utils.tag_modes import TagMode, get_tag_mode_config, get_tag_strategy


# =============================================================================
# Data Shapes for LLM Export
# =============================================================================

@dataclass
class TagExport:
    """Compact tag representation for LLM consumption."""
    id: int
    label: str          # Base name (e.g., "doctors")
    path: str           # Full path (e.g., "health/doctors")
    note_count: int     # Number of notes with this tag
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "path": self.path,
            "note_count": self.note_count,
        }


@dataclass
class NoteExport:
    """Compact note representation for LLM consumption."""
    id: int
    title: str | None
    content_preview: str  # First N chars for context
    tags: list[str]       # Tag paths or names based on mode
    created_at: str | None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "content_preview": self.content_preview,
            "tags": self.tags,
            "created_at": self.created_at,
        }


@dataclass
class LLMExportData:
    """
    Complete data package for LLM analysis.
    
    Contains all tags and notes in a format optimized for
    hierarchy reorganization suggestions.
    """
    mode: str                    # "path" or "flat"
    tags: list[TagExport] = field(default_factory=list)
    notes: list[NoteExport] = field(default_factory=list)
    statistics: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "tags": [t.to_dict() for t in self.tags],
            "notes": [n.to_dict() for n in self.notes],
            "statistics": self.statistics,
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        import json
        return json.dumps(self.to_dict(), indent=indent)


# =============================================================================
# Export Functions
# =============================================================================

def export_tags_for_llm(
    db: Session,
    include_note_counts: bool = True,
) -> list[TagExport]:
    """
    Export all tags in a compact format for LLM.
    
    Args:
        db: Database session
        include_note_counts: Whether to include note counts
        
    Returns:
        List of TagExport objects
    """
    tags = db.query(Tag).all()
    
    exports = []
    for tag in tags:
        note_count = len(tag.notes) if include_note_counts else 0
        exports.append(TagExport(
            id=tag.id,
            label=tag.label,
            path=tag.path,
            note_count=note_count,
        ))
    
    return exports


def export_notes_for_llm(
    db: Session,
    content_preview_length: int = 200,
    tag_mode: TagMode | None = None,
) -> list[NoteExport]:
    """
    Export all notes in a compact format for LLM.
    
    Args:
        db: Database session
        content_preview_length: How many characters of content to include
        tag_mode: Override tag mode (defaults to config)
        
    Returns:
        List of NoteExport objects
    """
    if tag_mode is None:
        tag_mode = get_tag_mode_config().mode
    
    strategy = get_tag_strategy(tag_mode)
    
    notes = db.query(Note).all()
    
    exports = []
    for note in notes:
        # Get content preview
        content = note.content or ""
        preview = content[:content_preview_length]
        if len(content) > content_preview_length:
            preview += "..."
        
        # Get tags based on mode
        tags = strategy.export_tags(note)
        
        created_at = note.created_at.isoformat() if note.created_at else None
        
        exports.append(NoteExport(
            id=note.id,
            title=note.title,
            content_preview=preview,
            tags=tags,
            created_at=created_at,
        ))
    
    return exports


def export_all_for_llm(db: Session) -> LLMExportData:
    """
    Export all data needed for LLM hierarchy analysis.
    
    Args:
        db: Database session
        
    Returns:
        Complete LLMExportData package
    """
    config = get_tag_mode_config()
    
    tags = export_tags_for_llm(db)
    notes = export_notes_for_llm(db, tag_mode=config.mode)
    
    # Compute statistics
    total_notes = db.query(Note).count()
    total_tags = db.query(Tag).count()
    avg_tags_per_note = sum(len(n.tags) for n in db.query(Note).all()) / max(total_notes, 1)
    
    statistics = {
        "total_notes": total_notes,
        "total_tags": total_tags,
        "avg_tags_per_note": round(avg_tags_per_note, 2),
        "mode": config.mode.value,
    }
    
    return LLMExportData(
        mode=config.mode.value,
        tags=tags,
        notes=notes,
        statistics=statistics,
    )


# =============================================================================
# LLM Response Shapes (for importing suggestions)
# =============================================================================

@dataclass
class TagMapping:
    """
    A mapping from old tag to new tag/location.
    
    Produced by LLM to suggest hierarchy changes.
    """
    old_tag_id: int
    new_path: str | None = None      # New hierarchical path (for path mode)
    new_label: str | None = None      # New flat label (for flat mode)
    merge_into_tag_id: int | None = None  # Merge with existing tag
    action: str = "keep"              # "keep", "rename", "merge", "delete"
    
    def to_dict(self) -> dict:
        return {
            "old_tag_id": self.old_tag_id,
            "new_path": self.new_path,
            "new_label": self.new_label,
            "merge_into_tag_id": self.merge_into_tag_id,
            "action": self.action,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "TagMapping":
        return cls(
            old_tag_id=data["old_tag_id"],
            new_path=data.get("new_path"),
            new_label=data.get("new_label"),
            merge_into_tag_id=data.get("merge_into_tag_id"),
            action=data.get("action", "keep"),
        )


@dataclass
class HierarchySuggestion:
    """
    Complete hierarchy reorganization suggestion from LLM.
    
    Contains tag mappings and optional new root categories.
    """
    tag_mappings: list[TagMapping] = field(default_factory=list)
    new_root_categories: list[str] = field(default_factory=list)
    reasoning: str = ""
    
    def to_dict(self) -> dict:
        return {
            "tag_mappings": [m.to_dict() for m in self.tag_mappings],
            "new_root_categories": self.new_root_categories,
            "reasoning": self.reasoning,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "HierarchySuggestion":
        return cls(
            tag_mappings=[TagMapping.from_dict(m) for m in data.get("tag_mappings", [])],
            new_root_categories=data.get("new_root_categories", []),
            reasoning=data.get("reasoning", ""),
        )


# =============================================================================
# Import Functions (Apply LLM Suggestions)
# =============================================================================

def apply_hierarchy_suggestions(
    db: Session,
    suggestions: HierarchySuggestion,
    dry_run: bool = True,
) -> dict:
    """
    Apply LLM-generated hierarchy suggestions to the database.
    
    Args:
        db: Database session
        suggestions: HierarchySuggestion from LLM
        dry_run: If True, don't commit changes
        
    Returns:
        Summary of changes made
    """
    from utils.tag_utils import get_or_create_tag_by_path
    
    changes = {
        "renamed": [],
        "merged": [],
        "deleted": [],
        "created": [],
        "errors": [],
    }
    
    # Process each mapping
    for mapping in suggestions.tag_mappings:
        tag = db.query(Tag).filter(Tag.id == mapping.old_tag_id).first()
        
        if not tag:
            changes["errors"].append(f"Tag ID {mapping.old_tag_id} not found")
            continue
        
        if mapping.action == "keep":
            continue
            
        elif mapping.action == "rename":
            if mapping.new_path:
                # Update the tag's path and hierarchy
                try:
                    # Create new tag at new path
                    new_tag = get_or_create_tag_by_path(db, mapping.new_path)
                    
                    # Move all notes from old tag to new tag
                    for note in tag.notes:
                        if new_tag not in note.tags:
                            note.tags.append(new_tag)
                    
                    changes["renamed"].append({
                        "old_path": tag.path,
                        "new_path": mapping.new_path,
                    })
                    
                    if not dry_run:
                        # Remove old tag (notes already moved)
                        db.delete(tag)
                        
                except Exception as e:
                    changes["errors"].append(f"Error renaming {tag.path}: {str(e)}")
                    
        elif mapping.action == "merge":
            if mapping.merge_into_tag_id:
                target = db.query(Tag).filter(Tag.id == mapping.merge_into_tag_id).first()
                if target:
                    # Move all notes to target
                    for note in tag.notes:
                        if target not in note.tags:
                            note.tags.append(target)
                    
                    changes["merged"].append({
                        "from": tag.path,
                        "to": target.path,
                    })
                    
                    if not dry_run:
                        db.delete(tag)
                else:
                    changes["errors"].append(f"Merge target {mapping.merge_into_tag_id} not found")
                    
        elif mapping.action == "delete":
            changes["deleted"].append(tag.path)
            if not dry_run:
                db.delete(tag)
    
    # Create new root categories if suggested
    for category in suggestions.new_root_categories:
        try:
            new_root = get_or_create_tag_by_path(db, category)
            changes["created"].append(category)
        except Exception as e:
            changes["errors"].append(f"Error creating {category}: {str(e)}")
    
    if not dry_run:
        db.commit()
    
    changes["dry_run"] = dry_run
    return changes


# =============================================================================
# Query Helpers for LLM-Generated Queries
# =============================================================================

def query_notes_by_tag_path_prefix(db: Session, prefix: str) -> list[Note]:
    """
    Query notes by tag path prefix (for subtree queries).
    
    Example: prefix="health" matches health/doctors, health/fitness, etc.
    """
    from models import Note, Tag
    
    # Normalize prefix
    prefix = prefix.strip("/")
    
    return (
        db.query(Note)
        .join(Note.tags)
        .filter(Tag.path.like(f"/{prefix}%"))
        .distinct()
        .all()
    )


def query_tags_in_subtree(db: Session, root_path: str) -> list[Tag]:
    """
    Get all tags in a subtree.
    
    Example: root_path="health" returns health, health/doctors, health/fitness, etc.
    """
    root_path = root_path.strip("/")
    
    return (
        db.query(Tag)
        .filter(Tag.path.like(f"/{root_path}%"))
        .all()
    )


def get_tag_hierarchy_tree(db: Session) -> dict:
    """
    Get complete tag hierarchy as a nested dict.
    
    Returns structure like:
    {
        "health": {
            "doctors": {},
            "fitness": {}
        },
        "work": {}
    }
    """
    tags = db.query(Tag).all()
    
    # Build tree
    tree = {}
    for tag in tags:
        parts = tag.path.strip("/").split("/")
        
        current = tree
        for part in parts:
            if part not in current:
                current[part] = {}
            current = current[part]
    
    return tree
