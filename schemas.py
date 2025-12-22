from pydantic import BaseModel
from typing import List, Optional


# --- Input Schemas (What you send) ---
class TagCreate(BaseModel):
    name: str


class NoteCreate(BaseModel):
    content: str
    tags: List[str] = []  # List of tag names, e.g. ["doctors", "health"]


# --- Output Schemas (What the API replies with) ---
class TagOut(BaseModel):
    name: str

    class Config:
        # form_attributes = True
        orm_mode = True  # Required for SQLAlchemy compatibility


class NoteOut(BaseModel):
    id: int
    content: Optional[str]
    media_path: Optional[str]
    media_type: str
    # tags: List[TagOut]
    tags: List[TagOut] = []

    class Config:
        # form_attributes = True
        orm_mode = True
