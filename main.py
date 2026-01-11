import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
import httpx

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import text
from sqlalchemy.orm import Session

try:
    import whisper
except Exception as e:
    print("Whisper not loaded:", e)
    whisper = None
from auth import create_access_token, verify_access_token
from config import Config
import db
from models import Note, User, Tag
from schemas import NoteCreate, NoteOut, UserCreate, UserOut
from db import get_db, init_db, reset_db
from dependencies import get_current_user
from utils.user_utils import add_user
from utils.password_utils import hash_password, verify_password
from utils.hierarchy_utils import load_hierarchy, flatten_hierarchy
from utils.note_utils import save_upload
from utils.tag_utils import get_or_create_tag, suggest_tags_from_text_semantic


UPLOAD_DIR = Path("static/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Load Whisper model once (small for CPU testing)
model = whisper.load_model("small")

# Temporary folder for audio files
TEMP_DIR = "./temp"
os.makedirs(TEMP_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    print("🚀 Starting application...")

    # Check if we should reset the database
    # should_reset = os.getenv("RESET_DB", "false").lower() == "true"
    should_reset = Config.RESET_DB

    if should_reset:
        print("⚠️  RESET_DB=true - Resetting database...")
        reset_db()
    else:
        init_db()

    # Load hierarchy data
    try:
        db.load_initial_data()
    except Exception as e:
        print(f"❌ Error loading hierarchy: {e}")

    print("✓ Application ready")

    yield

    # Shutdown
    print("👋 Shutting down application...")
    db.engine.dispose()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.post("/notes/", response_model=NoteOut)
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
    note = Note(content=content, media_type=media_type)

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
@app.post("/notes/", response_model=NoteOut)
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
    note = Note(content=content, media_type=media_type)
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
    # TODO: max img size here - aybe rename the note name plus id of the note
    ext = Path(file.filename).suffix.lower()
    note = Note(media_type="image")
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
        db_tag = db.query(Tag).filter_by(name=tag_name).first()
        if not db_tag:
            db_tag = Tag(name=tag_name)
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
        db.query(Note)
        .join(Note.tags)
        .filter(Tag.name.in_(relevant_tags))
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


# --- Sign up with username/password ---
@app.post("/users/", response_model=UserOut)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = (
        db.query(User)
        .filter((User.username == user.username) | (User.email == user.email))
        .first()
    )
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email already exists")

    db_user = User(
        username=user.username,
        email=user.email,
        password_hash=hash_password(user.password),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# create new user
@app.post("/users/", response_model=UserOut)
def create_user(user_in: UserCreate, db: Session = Depends(get_db)):
    # Check if username/email already exists
    if db.query(User).filter(User.username == user_in.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )
    if user_in.email and db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists",
        )

    # Create the user
    user = add_user(
        db,
        username=user_in.username,
        email=user_in.email,
        password_hash=user_in.password_hash,
        is_active=user_in.is_active,
    )
    return user


@app.get("/auth/github/callback")
def github_callback(code: str, db: Session = Depends(get_db)):
    # Exchange code for access token
    token_resp = httpx.post(
        "https://github.com/login/oauth/access_token",
        data={
            "client_id": Config.GITHUB_CLIENT_ID,
            "client_secret": Config.GITHUB_CLIENT_SECRET,
            "code": code,
        },
        headers={"Accept": "application/json"},
    ).json()

    access_token = token_resp.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="GitHub auth failed")

    # Get user info from GitHub
    user_info = httpx.get(
        "https://api.github.com/user",
        headers={"Authorization": f"token {access_token}"},
    ).json()

    username = user_info["login"]
    email = user_info.get("email") or f"{username}@github.com"

    # Check if user exists
    db_user = db.query(User).filter_by(email=email).first()
    if not db_user:
        db_user = User(username=username, email=email)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

    return {"username": db_user.username, "email": db_user.email}

    # In production, you’d generate a JWT or session cookie after login.


@app.post("/token")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    user = db.query(User).filter_by(username=form_data.username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    if not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/notes/protected")
def create_note_protected(
    note: NoteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    new_note = Note(content=note.content, media_type="text")
    new_note.user_id = current_user.id  # link note to user
    db.add(new_note)
    db.commit()
    db.refresh(new_note)
    return new_note


# @app.post("/upload_audio/")
# async def upload_audio(
#     file: UploadFile = File(...),
#     db: Session = Depends(get_db),
#     user=Depends(get_current_user),
# ):
#     print("➡️ ENTERED upload_audio")
#     print("Current user:", user)
#     print("Filename:", file.filename)
#     # Save temporary file
#     audio_path = os.path.join(TEMP_DIR, file.filename)
#     with open(audio_path, "wb") as f:
#         f.write(await file.read())

#     # Transcribe audio
#     try:
#         result = model.transcribe(audio_path)
#         transcription = result["text"]
#         print("Transcription:", result)

#     except Exception as e:
#         os.remove(audio_path)
#         raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")

#     os.remove(audio_path)  # delete temp file after processing

#     # Build flat_mapping from Tag table
#     tags_in_db = db.query(Tag).all()
#     flat_mapping = {tag.name: [] for tag in tags_in_db}

#     # Use your existing get_suggestions function
#     suggested_tags = get_suggestions(
#         selected_tags=[], current_input=transcription, flat_mapping=flat_mapping
#     )
#     print("Tags found:", suggested_tags)

#     return {"transcription": transcription, "tags": suggested_tags}


@app.post("/upload_audio/")
async def upload_audio(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    # user=Depends(get_current_user),
):
    # audio_path = save_temp(file)
    audio_path = os.path.join(TEMP_DIR, file.filename)

    with open(audio_path, "wb") as f:
        f.write(await file.read())

    try:
        result = model.transcribe(audio_path)
        text = result["text"]
    finally:
        os.remove(audio_path)

    # suggested_tags = suggest_tags_from_text(text, db)
    suggested_tags = suggest_tags_from_text_semantic(text, db)

    return {
        "transcription": text,
        "suggested_tags": suggested_tags,
    }
