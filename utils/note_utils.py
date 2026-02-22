from fastapi import UploadFile
from sqlalchemy.orm import Session
from pathlib import Path
import shutil
from typing import Optional


# =============================================================================
# File Upload Handling
# =============================================================================
def save_upload(file: UploadFile, note_id: int, upload_dir: Path) -> str:
    ext = Path(file.filename).suffix.lower()
    safe_filename = f"note_{note_id}{ext}"
    file_path = upload_dir / safe_filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return f"static/uploads/{safe_filename}"


def import_markdown_to_note(db: Session, md: str, owner_id: Optional[int] = None):
    from utils.markdown_utils import markdown_to_parsed_note
    from models import Note
    from utils.tag_utils import get_or_create_tag_by_path, get_or_create_tag
    
    parsed = markdown_to_parsed_note(md)
    
    note = Note(
        title=parsed.title,
        content=parsed.content,
        media_path=parsed.media_path,
        media_type=parsed.media_type or "text",
        created_at=parsed.created_at,
        updated_at=parsed.updated_at,
        owner_id=owner_id
    )
    
    # 1. Resolve hierarchical tag paths (e.g. "health/doctors")
    for tp in parsed.tag_paths:
        tag = get_or_create_tag_by_path(db, tp)
        if tag not in note.tags:
            note.tags.append(tag)
            
    # 2. Resolve simple tag names (e.g. "doctors")
    # This aligns with the user's desire to keep standard tags separated from their explicit path structures.
    for t_name in parsed.tags:
        tag = get_or_create_tag(db, t_name, auto_others=True)
        if tag not in note.tags:
            note.tags.append(tag)
            
    db.add(note)
    db.commit()
    db.refresh(note)
    
    return note