from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import List, Optional

from sqlalchemy import Boolean, Column, Integer, String

from db import Base


# --- Input Schemas (What you send) ---
class TagCreate(BaseModel):
    name: str


class TagResolveInput(BaseModel):
    label: str


class NoteCreate(BaseModel):
    content: str
    tags: List[str] = []  # List of tag names, e.g. ["doctors", "health"]


# --- Output Schemas (What the API replies with) ---
class TagOut(BaseModel):
    id: int
    label: str
    path: str

    class Config:
        model_config = ConfigDict(from_attributes=True)


class NoteOut(BaseModel):
    id: int
    content: Optional[str]
    media_path: Optional[str]
    media_type: str
    tags: List[TagOut]
    # tags: List[TagOut] = []

    class Config:
        model_config = ConfigDict(from_attributes=True)


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
