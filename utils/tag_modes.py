"""
Tag Mode Configuration and Strategy Pattern

This module provides a modular way to handle two tagging strategies:
- Mode A (path): Hierarchical tag paths like "health/doctors"
- Mode B (flat): Flat tags like "doctors", where hierarchy is inferred later by LLM

The mode can be switched via configuration without changing core logic.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from sqlalchemy.orm import Session

from models import Note, Tag
from utils.tag_utils import tag_processor


# =============================================================================
# Tag Mode Enum and Configuration
# =============================================================================

class TagMode(str, Enum):
    PATH = "path"  # Hierarchical paths (Mode A)
    FLAT = "flat"  # Flat tags with LLM inference (Mode B)


@dataclass
class TagModeConfig:
    """
    Configuration for tag handling behavior.
    
    Attributes:
        mode: Current tag mode (PATH or FLAT)
        disambiguation_enabled: Whether to ask user when ambiguous tags exist
        auto_create_tags: Whether to auto-create tags that don't exist
        default_parent: Default parent for new tags in path mode
    """
    mode: TagMode = TagMode.PATH
    disambiguation_enabled: bool = True
    auto_create_tags: bool = True
    default_parent: str | None = None  # e.g., "others" for flat mode
    
    @classmethod
    def from_env(cls) -> "TagModeConfig":
        """Create config from environment variables."""
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        mode_str = os.getenv("TAG_MODE", "path").lower()
        mode = TagMode.PATH if mode_str == "path" else TagMode.FLAT
        
        return cls(
            mode=mode,
            disambiguation_enabled=os.getenv("TAG_DISAMBIGUATION_ENABLED", "true").lower() == "true",
            auto_create_tags=os.getenv("TAG_AUTO_CREATE", "true").lower() == "true",
            default_parent=os.getenv("TAG_DEFAULT_PARENT", None),
        )


# Global config instance
_config: TagModeConfig | None = None


def get_tag_mode_config() -> TagModeConfig:
    """Get the current tag mode configuration."""
    global _config
    if _config is None:
        _config = TagModeConfig.from_env()
    return _config


def set_tag_mode_config(config: TagModeConfig) -> None:
    """Set the tag mode configuration (useful for testing)."""
    global _config
    _config = config


# =============================================================================
# Tag Resolution Result Types
# =============================================================================

@dataclass
class TagCandidate:
    """A potential tag match for resolution."""
    id: int
    label: str  # Base name like "doctors"
    path: str   # Full path like "health/doctors" (or "/" for flat)
    
    def to_dict(self) -> dict:
        return {"id": self.id, "label": self.label, "path": self.path}


@dataclass
class TagResolutionResult:
    """
    Result of tag name resolution.
    
    Status can be:
    - unique_match: Exactly one tag found - can auto-attach
    - multiple_matches: Multiple tags found - frontend should ask user
    - not_found: No tags found - can create new or suggest parents
    """
    status: Literal["unique_match", "multiple_matches", "not_found"]
    selected_tag: TagCandidate | None = None  # For unique_match
    candidates: list[TagCandidate] = field(default_factory=list)  # For multiple_matches
    suggested_parents: list[TagCandidate] = field(default_factory=list)  # For not_found in path mode
    can_create: bool = True  # Whether user can create a new tag
    context_hint: str | None = None  # Explanation of why auto-resolved (e.g., "Matched based on existing tags")
    
    def to_dict(self) -> dict:
        result = {
            "status": self.status,
            "can_create": self.can_create,
        }
        if self.selected_tag:
            result["tag"] = self.selected_tag.to_dict()
        if self.candidates:
            result["candidates"] = [c.to_dict() for c in self.candidates]
        if self.suggested_parents:
            result["suggested_parents"] = [p.to_dict() for p in self.suggested_parents]
        if self.context_hint:
            result["context_hint"] = self.context_hint
        return result


# =============================================================================
# Tag Strategy Interface (Abstract Base)
# =============================================================================

class TagStrategy(ABC):
    """
    Abstract base class for tag strategies.
    
    Implement this to add new tag handling modes.
    """
    
    @property
    @abstractmethod
    def mode(self) -> TagMode:
        """Return the tag mode this strategy handles."""
        pass
    
    @abstractmethod
    def resolve_tag(self, db: Session, name: str) -> TagResolutionResult:
        """
        Resolve a tag name to actual tag(s).
        
        Args:
            db: Database session
            name: Tag name to resolve (e.g., "doctors" or "health/doctors")
            
        Returns:
            TagResolutionResult with status and candidates
        """
        pass
    
    @abstractmethod
    def get_or_create_tag(
        self, db: Session, name: str, parent: Tag | None = None
    ) -> Tag:
        """
        Get or create a tag with this strategy's rules.
        
        Args:
            db: Database session
            name: Tag name (could be path in path mode)
            parent: Optional parent tag
            
        Returns:
            Created or existing Tag
        """
        pass
    
    @abstractmethod
    def get_notes_by_tag(self, db: Session, tag_name: str) -> list[Note]:
        """
        Get all notes associated with a tag.
        
        Args:
            db: Database session
            tag_name: Tag name or path
            
        Returns:
            List of notes
        """
        pass
    
    @abstractmethod
    def export_tags(self, note: Note) -> list[str]:
        """
        Export tags from a note in this mode's format.
        
        Args:
            note: Note to export tags from
            
        Returns:
            List of tag strings (paths or names based on mode)
        """
        pass
    
    @abstractmethod
    def import_tags(self, db: Session, tag_strings: list[str]) -> list[Tag]:
        """
        Import tags from strings in this mode's format.
        
        Args:
            db: Database session
            tag_strings: List of tag paths or names
            
        Returns:
            List of resolved Tag objects
        """
        pass


# =============================================================================
# Mode A: Path-Based Tag Strategy
# =============================================================================

class PathTagStrategy(TagStrategy):
    """
    Strategy for hierarchical path-based tags (Mode A).
    
    Example: "health/doctors", "kids/doctors"
    
    Supports context-aware resolution: when a note already has tags like
    "endocrinologist" (under health), adding "doctors" will prioritize
    "health/doctors" over other "doctors" variants.
    """
    
    @property
    def mode(self) -> TagMode:
        return TagMode.PATH
    
    def resolve_tag(
        self,
        db: Session,
        name: str,
        existing_tags: list[str] | None = None,
    ) -> TagResolutionResult:
        """
        Resolve a tag by path or name.
        
        If name contains "/", treat as full path.
        Otherwise, search for all tags with that base name.
        
        Args:
            db: Database session
            name: Tag name to resolve (e.g., "doctors" or "health/doctors")
            existing_tags: List of existing tag labels on the note for context-aware resolution
                          (e.g., ["endocrinologist"] to prioritize health/doctors)
        """
        config = get_tag_mode_config()
        
        # Normalize the input
        normalized = tag_processor.normalize(name)
        
        # Check if it's a full path (contains "/")
        if "/" in name:
            # Direct path lookup
            slug_path = "/".join([
                tag_processor.slugify(p) for p in name.strip("/").split("/")
            ])
            full_path = f"/{slug_path}"
            
            tag = db.query(Tag).filter(Tag.path == full_path).first()
            if tag:
                return TagResolutionResult(
                    status="unique_match",
                    selected_tag=TagCandidate(
                        id=tag.id,
                        label=tag.label,
                        path=tag.path
                    )
                )
            return TagResolutionResult(status="not_found", can_create=config.auto_create_tags)
        
        # It's a base name - find all tags with that label
        tags = db.query(Tag).filter(Tag.label == normalized).all()
        
        if len(tags) == 0:
            # No tags found - suggest possible parents
            return TagResolutionResult(
                status="not_found",
                can_create=config.auto_create_tags,
                suggested_parents=self._suggest_parent_categories(db, normalized)
            )
        elif len(tags) == 1:
            return TagResolutionResult(
                status="unique_match",
                selected_tag=TagCandidate(
                    id=tags[0].id,
                    label=tags[0].label,
                    path=tags[0].path
                )
            )
        else:
            # Multiple matches - check if we can resolve by context
            if existing_tags and config.disambiguation_enabled:
                # Try to find the best match based on existing tags
                best_match = self._resolve_by_context(db, tags, existing_tags)
                if best_match:
                    return TagResolutionResult(
                        status="unique_match",
                        selected_tag=TagCandidate(
                            id=best_match.id,
                            label=best_match.label,
                            path=best_match.path
                        ),
                        context_hint=f"Matched based on existing tags: {existing_tags}"
                    )
            
            # Return all candidates for user to choose
            return TagResolutionResult(
                status="multiple_matches",
                candidates=[
                    TagCandidate(id=t.id, label=t.label, path=t.path)
                    for t in tags
                ],
                can_create=config.auto_create_tags
            )
    
    def _resolve_by_context(
        self,
        db: Session,
        candidates: list[Tag],
        existing_labels: list[str],
    ) -> Tag | None:
        """
        Resolve ambiguous tags using existing note tags as context.
        
        If note has "endocrinologist" (path: /health/doctors/endocrinologist),
        and we're adding "doctors", we prioritize /health/doctors.
        
        Args:
            candidates: List of candidate tags with the same label
            existing_labels: List of existing tag labels on the note
            
        Returns:
            The best matching tag, or None if no clear match
        """
        if not existing_labels or not candidates:
            return None
        
        # Get full paths for all existing tags
        existing_paths = set()
        for label in existing_labels:
            normalized = tag_processor.normalize(label)
            existing_tag = db.query(Tag).filter(Tag.label == normalized).first()
            if existing_tag:
                existing_paths.add(existing_tag.path)
        
        # For each candidate, check if any existing tag shares a common parent
        # e.g., /health/doctors/endocrinologist shares /health with /health/doctors
        best_candidate = None
        best_match_length = 0
        
        for candidate in candidates:
            candidate_parts = candidate.path.strip("/").split("/")
            
            for existing_path in existing_paths:
                existing_parts = existing_path.strip("/").split("/")
                
                # Find common prefix length
                common_length = 0
                for i, (cp, ep) in enumerate(zip(candidate_parts, existing_parts)):
                    if cp == ep:
                        common_length += 1
                    else:
                        break
                
                # If candidate is a parent of an existing tag, it's a good match
                # e.g., /health/doctors is parent of /health/doctors/endocrinologist
                if common_length >= len(candidate_parts) - 1:
                    if common_length > best_match_length:
                        best_match_length = common_length
                        best_candidate = candidate
        
        return best_candidate
    
    def _suggest_parent_categories(self, db: Session, name: str) -> list[TagCandidate]:
        """
        Suggest existing categories that could be parents for a new tag.
        Only returns suggestions if there are related matches - not random categories.
        """
        # Only suggest if the tag name has some similarity to existing tags
        # Otherwise return empty list - don't confuse users with random suggestions
        normalized = tag_processor.normalize(name)
        
        # Look for tags that contain the search term (partial match)
        similar_tags = db.query(Tag).filter(
            Tag.label.ilike(f"%{normalized}%")
        ).limit(5).all()
        
        if similar_tags:
            return [
                TagCandidate(id=t.id, label=t.label, path=t.path)
                for t in similar_tags
            ]
        
        # No similar tags found - return empty list
        # User can still create new tag under "others"
        return []
    
    def get_or_create_tag(
        self, db: Session, name: str, parent: Tag | None = None
    ) -> Tag:
        """Get or create a tag by path."""
        from utils.tag_utils import get_or_create_tag_by_path
        return get_or_create_tag_by_path(db, name)
    
    def get_notes_by_tag(self, db: Session, tag_name: str) -> list[Note]:
        """Get notes by tag path or subtree."""
        from utils.tag_utils import get_notes_by_subtree
        return get_notes_by_subtree(db, tag_name)
    
    def export_tags(self, note: Note) -> list[str]:
        """Export tags as paths."""
        return [tag.path for tag in note.tags]
    
    def import_tags(self, db: Session, tag_strings: list[str]) -> list[Tag]:
        """Import tags from paths."""
        from utils.tag_utils import get_or_create_tag_by_path
        tags = []
        for path in tag_strings:
            tag = get_or_create_tag_by_path(db, path)
            tags.append(tag)
        return tags


# =============================================================================
# Mode B: Flat Tag Strategy
# =============================================================================

class FlatTagStrategy(TagStrategy):
    """
    Strategy for flat tags (Mode B).
    
    All tags are stored as flat names. Hierarchy is inferred by LLM later.
    Example: "doctors", "pediatrics"
    """
    
    @property
    def mode(self) -> TagMode:
        return TagMode.FLAT
    
    def resolve_tag(self, db: Session, name: str) -> TagResolutionResult:
        """
        Resolve a flat tag name.
        
        Since all tags are flat, we just look up by normalized name.
        """
        config = get_tag_mode_config()
        
        # Normalize the input
        normalized = tag_processor.normalize(name)
        
        # Look up by label (flat - no path consideration)
        tags = db.query(Tag).filter(Tag.label == normalized).all()
        
        if len(tags) == 0:
            return TagResolutionResult(
                status="not_found",
                can_create=config.auto_create_tags
            )
        elif len(tags) == 1:
            return TagResolutionResult(
                status="unique_match",
                selected_tag=TagCandidate(
                    id=tags[0].id,
                    label=tags[0].label,
                    path=tags[0].path  # Will be flat like "/doctors"
                )
            )
        else:
            # In flat mode, duplicates shouldn't happen due to DB constraints
            # But handle gracefully
            return TagResolutionResult(
                status="multiple_matches",
                candidates=[
                    TagCandidate(id=t.id, label=t.label, path=t.path)
                    for t in tags
                ]
            )
    
    def get_or_create_tag(
        self, db: Session, name: str, parent: Tag | None = None
    ) -> Tag:
        """Get or create a flat tag."""
        from utils.tag_utils import get_or_create_tag
        
        # In flat mode, ignore parent - all tags are flat
        return get_or_create_tag(db, name, parent=None, auto_others=True)
    
    def get_notes_by_tag(self, db: Session, tag_name: str) -> list[Note]:
        """Get notes by flat tag name."""
        normalized = tag_processor.normalize(tag_name)
        return (
            db.query(Note)
            .join(Note.tags)
            .filter(Tag.label == normalized)
            .distinct()
            .all()
        )
    
    def export_tags(self, note: Note) -> list[str]:
        """Export tags as flat names."""
        return [tag.label for tag in note.tags]
    
    def import_tags(self, db: Session, tag_strings: list[str]) -> list[Tag]:
        """Import tags as flat names."""
        tags = []
        for name in tag_strings:
            tag = self.get_or_create_tag(db, name)
            tags.append(tag)
        return tags


# =============================================================================
# Strategy Registry
# =============================================================================

_STRATEGIES: dict[TagMode, TagStrategy] = {
    TagMode.PATH: PathTagStrategy(),
    TagMode.FLAT: FlatTagStrategy(),
}


def get_tag_strategy(mode: TagMode | None = None) -> TagStrategy:
    """Get the tag strategy for the given mode or current config mode."""
    if mode is None:
        mode = get_tag_mode_config().mode
    return _STRATEGIES[mode]


def get_current_strategy() -> TagStrategy:
    """Get the strategy for the current configured mode."""
    return get_tag_strategy(get_tag_mode_config().mode)


# =============================================================================
# Convenience Functions (use current strategy)
# =============================================================================

def resolve_tag(name: str, db: Session) -> TagResolutionResult:
    """Resolve a tag name using the current strategy."""
    return get_current_strategy().resolve_tag(db, name)


def resolve_tag_for_mode(name: str, db: Session, mode: TagMode) -> TagResolutionResult:
    """Resolve a tag name using a specific mode's strategy."""
    return get_tag_strategy(mode).resolve_tag(db, name)


def get_or_create_tag(name: str, db: Session, parent: Tag | None = None) -> Tag:
    """Get or create a tag using the current strategy."""
    return get_current_strategy().get_or_create_tag(db, name, parent)


def get_notes_by_tag(tag_name: str, db: Session) -> list[Note]:
    """Get notes by tag using the current strategy."""
    return get_current_strategy().get_notes_by_tag(db, tag_name)


def export_note_tags(note: Note) -> list[str]:
    """Export tags from a note using the current strategy."""
    return get_current_strategy().export_tags(note)


def import_note_tags(tag_strings: list[str], db: Session) -> list[Tag]:
    """Import tags for a note using the current strategy."""
    return get_current_strategy().import_tags(db, tag_strings)
