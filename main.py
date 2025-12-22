from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path
import shutil
import os
from sqlalchemy import text
import models, schemas, database
from utils import flatten_hierarchy, load_hierarchy, add_tags

app = FastAPI()

UPLOAD_DIR = Path("static/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")


# --- STARTUP EVENT: Create tables & populate hierarchy ---
# @app.onstart("startup")
# async def on_startup():
@asynccontextmanager
async def lifespan(app: FastAPI):
    with database.engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON;"))  # 🔥 KLUCZOWE
        conn.execute(text("PRAGMA journal_mode = WAL;"))
        # conn.execute(text("PRAGMA journal_mode=WAL;"))

    DEV_RESET = os.getenv("RESET_DB", "false").lower() == "true"

    if DEV_RESET:
        database.reset_db()
    else:
        database.init_db()

    db = database.SessionLocal()
    try:
        hierarchy = load_hierarchy("hierarchy.json")
        add_tags(hierarchy, db=db)
    finally:
        db.close()


# --- DEPENDENCY: Database session per request ---
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/notes/", response_model=schemas.NoteOut)
def create_note(
    # content: Optional[str] = Form(None),
    # file: Optional[UploadFile] = File(None),
    # tags: str = Form(""),
    # db: Session = Depends(get_db),
    content: str = Form(""),
    tags: str = Form(""),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):

    if not content.strip() and not file:
        raise HTTPException(
            status_code=400,
            detail="Note must contain text or an image.",
        )

    # media_type = "text" if not file else "image"
    media_type = "image" if file else "text"
    note = models.Note(content=content, media_type=media_type)

    db.add(note)
    db.flush()

    # handle image
    if file:
        ext = Path(file.filename).suffix.lower()
        safe_filename = f"note_{note.id}{ext}"
        file_path = UPLOAD_DIR / safe_filename

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        note.media_path = f"static/uploads/{safe_filename}"
        # ten flush

    # handle tags
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

    return note


# @app.post("/notes/", response_model=schemas.NoteOut)
# def create_note(
#     content: Optional[str] = Form(None),
#     file: Optional[UploadFile] = File(None),
#     tags: str = Form(""),
#     db: Session = Depends(get_db),
# ):
#     # 1. Create note
#     media_type = "text" if not file else "image"
#     note = models.Note(content=content, media_type=media_type)
#     db.add(note)
#     db.commit()
#     db.refresh(note)

#     # 2. Handle image if provided
#     if file:
#         ext = Path(file.filename).suffix.lower()
#         safe_filename = f"note_{note.id}{ext}"
#         file_path = UPLOAD_DIR / safe_filename

#         with open(file_path, "wb") as buffer:
#             shutil.copyfileobj(file.file, buffer)

#         note.media_path = f"static/uploads/{safe_filename}"
#         # note.media_type = "image"
#         db.commit()
#         db.refresh(note)

#     # 3. Handle tags
#     tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
#     for tag_name in tag_list:
#         db_tag = db.query(models.Tag).filter_by(name=tag_name).first()
#         if not db_tag:
#             db_tag = models.Tag(name=tag_name)
#             db.add(db_tag)
#             db.flush()  # assign ID without committing
#         note.tags.append(db_tag)
#     db.commit()
#     db.refresh(note)
#     return note


# --- ENDPOINT 1: Create Text Note ---
# @app.post("/notes/", response_model=schemas.NoteOut)
# def create_note(note: schemas.NoteCreate, db: Session = Depends(database.get_db)):
#     # 1. Create the Note
#     new_note = models.Note(content=note.content, media_type="text")
#     # 2. Handle Tags
#     for tag_name in note.tags:
#         tag_name = tag_name.lower().strip()
#         # Check if tag exists, if not create it
#         db_tag = db.query(models.Tag).filter(models.Tag.name == tag_name).first()
#         if not db_tag:
#             db_tag = models.Tag(name=tag_name)
#             db.add(db_tag)
#             db.commit()  # Commit to get ID
#             db.refresh(db_tag)

#         new_note.tags.append(db_tag)

#     db.add(new_note)
#     db.commit()
#     db.refresh(new_note)
#     return new_note


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
    # 1. Create note FIRST
    media_type = "text" if not file else "image"
    note = models.Note(content=content, media_type=media_type)
    db.add(note)
    # db.commit()
    # db.refresh(note)
    db.add(note)
    db.flush()  # Assigns note.id for file handling

    # 2. Build safe filename
    # ext = Path(file.filename).suffix.lower()
    # filename = f"note_{note.id}{ext}"
    # file_path = UPLOAD_DIR / filename
    if file:
        ext = Path(file.filename).suffix.lower()
        safe_filename = f"note_{note.id}{ext}"
        file_path = UPLOAD_DIR / safe_filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        note.media_path = f"static/uploads/{safe_filename}"
        # db.commit()
        # db.refresh(note)

    # Handle tags
    tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
    for tag_name in tag_list:
        db_tag = db.query(models.Tag).filter_by(name=tag_name).first()
        if not db_tag:
            db_tag = models.Tag(name=tag_name)
            db.add(db_tag)
            db.flush()  # assign ID without commit
        note.tags.append(db_tag)

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
