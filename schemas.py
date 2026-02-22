from enum import Enum
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import List, Literal, Optional

from sqlalchemy import Boolean, Column, Integer, String

from db import Base
from datetime import datetime
from typing import List, Optional


# =============================================================================
# Tag Mode Schemas
# =============================================================================

class TagMode(str, Enum):
    """Tag mode: path (hierarchical) or flat."""
    PATH = "path"
    FLAT = "flat"


# --- Tag Resolution Schemas ---

class TagCandidateOut(BaseModel):
    """A potential tag match for resolution."""
    id: int
    label: str  # Base name like "doctors"
    path: str   # Full path like "health/doctors"
    
    class Config:
        model_config = ConfigDict(from_attributes=True)


class TagResolveInput(BaseModel):
    """Input for tag resolution."""
    label: str = Field(..., description="Tag name to resolve (e.g., 'doctors')")
    mode: Optional[TagMode] = Field(None, description="Override tag mode (defaults to config)")
    note_id: Optional[int] = Field(None, description="Note ID for context-aware resolution")
    note_tags: Optional[List[str]] = Field(None, description="Existing tag labels on the note for context")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {"label": "doctors"},
                {"label": "doctors", "note_tags": ["endocrinologist"]},
                {"label": "health/doctors", "mode": "path"},
            ]
        }
    }


class TagResolveOutput(BaseModel):
    """Output from tag resolution."""
    status: Literal["unique_match", "multiple_matches", "not_found"]
    can_create: bool = True
    tag: Optional[TagCandidateOut] = None
    candidates: List[TagCandidateOut] = []
    suggested_parents: List[TagCandidateOut] = []
    
    def to_dict(self) -> dict:
        result = {
            "status": self.status,
            "can_create": self.can_create,
        }
        if self.tag:
            result["tag"] = self.tag.model_dump()
        if self.candidates:
            result["candidates"] = [c.model_dump() for c in self.candidates]
        if self.suggested_parents:
            result["suggested_parents"] = [p.model_dump() for p in self.suggested_parents]
        return result


class TagCreateInput(BaseModel):
    """Input for creating a new tag."""
    label: str = Field(..., description="Tag name or path")
    parent_path: Optional[str] = Field(None, description="Parent path for path mode")
    mode: Optional[TagMode] = Field(None, description="Tag mode (defaults to config)")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {"label": "doctors"},
                {"label": "cardiologist", "parent_path": "health/doctors"},
            ]
        }
    }


class TagAttachInput(BaseModel):
    """Input for attaching an existing tag to a note."""
    tag_id: int = Field(..., description="ID of the tag to attach")
    note_id: int = Field(..., description="ID of the note to attach to")


# --- Input Schemas (What you send) ---
class TagCreate(BaseModel):
    name: str


class NoteCreate(BaseModel):
    content: str
    tags: List[str] = []  # List of tag names, e.g. ["doctors", "health"]


class TagStatsOut(BaseModel):
    total_count: int | None = None
    last_24h_count: int | None = None
    last_7d_count: int | None = None
    trending_score: float | None = None
    last_used_at: datetime | None = None


# --- Output Schemas (What the API replies with) ---
class TagOut(BaseModel):
    id: int
    label: str
    path: str
    stats: TagStatsOut | None = None

    class Config:
        model_config = ConfigDict(from_attributes=True)


class NoteOut(BaseModel):
    id: int
    title: Optional[str] = None
    content: Optional[str] = None
    media_path: Optional[str] = None
    media_type: Optional[str] = None
    link: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    tags: List[TagOut]

    class Config:
        model_config = ConfigDict(from_attributes=True)


class ParsedNote(BaseModel):
    id: Optional[int] = None
    title: Optional[str] = None
    author: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    tags: List[str] = []        # Simple names like 'doctors'
    tag_paths: List[str] = []   # Hierarchical paths like 'health/doctors'
    media_path: Optional[str] = None
    media_type: Optional[str] = None
    content: str


class UserCreate(BaseModel):
    username: str = Field(..., min_length=4)
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool

    class Config:
        model_config = ConfigDict(from_attributes=True)
