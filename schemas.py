from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional

from sqlalchemy import Boolean, Column, Integer, String

from database import Base


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
        orm_mode = True


class NoteOut(BaseModel):
    id: int
    content: Optional[str]
    media_path: Optional[str]
    media_type: str
    # tags: List[TagOut]
    tags: List[TagOut] = []

    class Config:
        orm_mode = True


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
        orm_mode = True
