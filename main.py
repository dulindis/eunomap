import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

import database
import models
import schemas
from database import get_db, init_db, reset_db
from utils import (
    flatten_hierarchy,
    get_or_create_tag,
    load_hierarchy,
    save_upload,
)

UPLOAD_DIR = Path("static/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    print("🚀 Starting application...")

    # Check if we should reset the database
    should_reset = os.getenv("RESET_DB", "false").lower() == "true"

    if should_reset:
        print("⚠️  RESET_DB=true - Resetting database...")
        reset_db()
    else:
        init_db()

    # Load hierarchy data
    try:
        database.load_initial_data()
    except Exception as e:
        print(f"❌ Error loading hierarchy: {e}")

    print("✓ Application ready")

    yield

    # Shutdown
    print("👋 Shutting down application...")
    database.engine.dispose()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.post("/notes/", response_model=schemas.NoteOut)
def create_note(
    content: str = Form(""),
    tags: str = Form(""),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    print(f"=== CREATE NOTE CALLED: content={content}, tags={tags} ===")  # ← Add this

    if not content.strip() and not file:
        raise HTTPException(
            status_code=400,
            detail="Note must contain text or an image.",
        )

    media_type = "image" if file else "text"
    note = models.Note(content=content, media_type=media_type)

    db.add(note)
    db.flush()

    # handle image
    if file:
        note.media_path = save_upload(file, note.id, UPLOAD_DIR)

        # handle tags
    tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
    print(f"Processing tags: {tag_list}")  # Add this debug line
    for tag_name in tag_list:
        print(f"Calling get_or_create_tag for: {tag_name}")  # Add this debug line
        db_tag = get_or_create_tag(db, tag_name)  # ← This line is critical!
        print(f"Got tag back: {db_tag.name}")  # Add this debug line
        note.tags.append(db_tag)

    db.commit()
    db.refresh(note)

    return note


# --- ENDPOINT 2: Upload Image (Drag & Drop Handler) ---
@app.post("/notes/", response_model=schemas.NoteOut)
def create_note(
    content: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    tags: str = Form(""),
    db: Session = Depends(get_db),
):
    if not content and not file:
        raise HTTPException(
            status_code=400, detail="Either content or file is required."
        )

    media_type = "text" if not file else "image"
    note = models.Note(content=content, media_type=media_type)
    db.add(note)

    db.add(note)
    db.flush()

    if file:
        ext = Path(file.filename).suffix.lower()
        safe_filename = f"note_{note.id}{ext}"
        file_path = UPLOAD_DIR / safe_filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        note.media_path = f"static/uploads/{safe_filename}"

    tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
    for tag_name in tag_list:
        tag = get_or_create_tag(db, tag_name, auto_others=True)
        note.tags.append(tag)

    db.commit()
    db.refresh(note)
    return note


# --- ENDPOINT 2: Upload Image ---
@app.post("/upload/")
def upload_image(
    file: UploadFile = File(...),
    tags: str = Form(...),
    db: Session = Depends(get_db),
):
    ext = Path(file.filename).suffix.lower()
    note = models.Note(media_type="image")
    db.add(note)
    db.commit()
    db.refresh(note)

    filename = f"note_{note.id}{ext}"
    file_path = UPLOAD_DIR / filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    note.media_path = f"static/uploads/{filename}"

    # Handle tags
    tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
    for tag_name in tag_list:
        db_tag = db.query(models.Tag).filter_by(name=tag_name).first()
        if not db_tag:
            db_tag = models.Tag(name=tag_name)
            db.add(db_tag)
            db.flush()
        note.tags.append(db_tag)

    db.commit()
    db.refresh(note)
    return {"info": "File saved", "path": note.media_path}

    # file_location = f"static/uploads/{file.filename}"
    # with open(file_location, "wb+") as buffer:
    #     shutil.copyfileobj(file.file, buffer)

    # new_note = models.Note(
    #     content=f"Image: {file.filename}", media_path=file_location, media_type="image"
    # )

    # tag_list = tags.split(",")
    # for tag_name in tag_list:
    #     tag_name = tag_name.lower().strip()
    #     if not tag_name:
    #         continue
    #     db_tag = db.query(models.Tag).filter(models.Tag.name == tag_name).first()
    #     if not db_tag:
    #         db_tag = models.Tag(name=tag_name)
    #         db.add(db_tag)
    #         db.commit()
    #         db.refresh(db_tag)
    #     new_note.tags.append(db_tag)

    # db.add(new_note)
    # db.commit()
    # return {"info": "File saved", "path": file_location}


# --- ENDPOINT 3: Generate Wiki Page ---
@app.get("/generate/{topic}")
def generate_wiki_page(topic: str, db: Session = Depends(get_db)):
    topic = topic.lower()
    hierarchy = load_hierarchy()
    subsections = flatten_hierarchy(topic, hierarchy)
    relevant_tags = [topic] + subsections

    notes = (
        db.query(models.Note)
        .join(models.Note.tags)
        .filter(models.Tag.name.in_(relevant_tags))
        .distinct()
        .all()
    )

    result = {
        "title": topic.upper(),
        "sections": {sub: [] for sub in subsections},
        "remaining": [],
    }

    for note in notes:
        note_tags = [t.name for t in note.tags]
        placed_in_section = False

        for sub in subsections:
            if sub in note_tags:
                result["sections"][sub].append(
                    {
                        "content": note.content,
                        "media": note.media_path,
                        "tags": note_tags,
                    }
                )
                placed_in_section = True

        if not placed_in_section:
            result["remaining"].append(
                {"content": note.content, "media": note.media_path, "tags": note_tags}
            )

    return result
