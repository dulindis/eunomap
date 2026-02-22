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

# Load Whisper model once (small for CPU testing)
try:
    if whisper:
        model = whisper.load_model("small")
    else:
        model = None
except Exception as e:
    print("Whisper model not loaded:", e)
    model = None

from auth import create_access_token, verify_access_token
from config import Config
import db
from models import Note, User, Tag
from schemas import (
    NoteCreate,
    NoteOut,
    UserCreate,
    UserOut,
    TagResolveInput,
    TagCreateInput,
    TagAttachInput,
)
from db import get_db, init_db, reset_db
from dependencies import get_current_user
from utils.user_utils import add_user
from utils.password_utils import hash_password, verify_password
from utils.hierarchy_utils import load_hierarchy, flatten_hierarchy
from utils.note_utils import save_upload
from utils.tag_utils import get_or_create_tag, suggest_tags_from_text_semantic


UPLOAD_DIR = Path("static/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# (model loading moved to try block above)

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


@app.get("/")
def read_root():
    """
    Root endpoint - redirects to the Streamlit UI or provides info.
    """
    from fastapi.responses import HTMLResponse

    html_content = """
    <!DOCTYPE html>
    <html>
        <head>
            <title>Eunomap - Personal Notes Manager</title>
            <meta http-equiv="refresh" content="0;url=http://localhost:8501">
        </head>
        <body>
            <p>Redirecting to <a href="http://localhost:8501">Streamlit App</a>...</p>
            <p>If not redirected, click: <a href="http://localhost:8501">http://localhost:8501</a></p>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)


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

    # First pass: resolve all tags, collecting existing tags for context
    resolved_tags = []
    from utils.tag_utils import tag_processor

    for tag_name in tag_list:
        normalized_key = tag_processor.normalize(tag_name)

        # Find ALL tags with this key (there might be multiple in different hierarchies)
        existing_tags = db.query(Tag).filter(Tag.key == normalized_key).all()

        if len(existing_tags) == 0:
            # No existing tag found, will create later
            resolved_tags.append((tag_name, None, existing_tags))
        elif len(existing_tags) == 1:
            # Single match - use it
            resolved_tags.append((tag_name, existing_tags[0], existing_tags))
        else:
            # Multiple matches - will resolve with context after we have all tags
            resolved_tags.append((tag_name, None, existing_tags))

    # Second pass: resolve ambiguous tags using context from already-resolved tags
    # Build context from tags we've already resolved
    context_paths = set()
    for tag_name, tag, _ in resolved_tags:
        if tag:
            context_paths.add(tag.path)

    # Now resolve ambiguous tags using context
    final_tags = []
    for tag_name, initial_tag, candidates in resolved_tags:
        if initial_tag:
            # Already resolved uniquely
            final_tags.append(initial_tag)
        elif candidates:
            # Multiple matches - find best using context
            best_tag = _resolve_tag_by_context_paths(candidates, context_paths)
            if best_tag:
                final_tags.append(best_tag)
            else:
                # No clear winner - pick the first one (or could show UI to choose)
                final_tags.append(candidates[0])
        else:
            # No existing tags - create new one
            # Check if we can place it under an existing tag from the note
            parent_tag = _find_best_parent_for_new_tag(db, tag_name, context_paths)
            if parent_tag:
                from utils.tag_utils import get_or_create_tag

                new_tag = get_or_create_tag(
                    db, tag_name, parent=parent_tag, auto_others=False
                )
            else:
                new_tag = get_or_create_tag(db, tag_name, auto_others=True)
            final_tags.append(new_tag)

    # Add all tags to note
    for tag in final_tags:
        note.tags.append(tag)

    db.commit()
    db.refresh(note)
    return note


def _resolve_tag_by_context_paths(candidates: list, context_paths: set) -> "Tag | None":
    """
    Resolve ambiguous tags using paths from other tags in the note as context.
    If we have 'cats' with path '/pets/cats' and 'health', prefer '/pets/health' over '/health'.
    """
    if not context_paths or not candidates:
        return None

    best_candidate = None
    best_match_length = 0

    for candidate in candidates:
        candidate_parts = candidate.path.strip("/").split("/")

        for context_path in context_paths:
            context_parts = context_path.strip("/").split("/")

            # Find common prefix length
            common_length = 0
            for i, (cp, ct) in enumerate(zip(candidate_parts, context_parts)):
                if cp == ct:
                    common_length += 1
                else:
                    break

            # Prefer candidates that share a common parent with context
            # e.g., /pets/health shares /pets with /pets/cats
            if (
                common_length >= len(context_parts)
                and common_length > best_match_length
            ):
                best_match_length = common_length
                best_candidate = candidate

    return best_candidate


def _find_best_parent_for_new_tag(
    db: Session, tag_name: str, context_paths: set
) -> "Tag | None":
    """
    Find the best parent tag for a new tag based on context from other tags.
    If we have 'cats' (path /pets/cats) and add 'food', prefer /pets/food over /others/food.
    """
    if not context_paths:
        return None

    from utils.tag_utils import tag_processor

    normalized = tag_processor.normalize(tag_name)

    # For each context path, try to find a parent that could be a sibling
    for context_path in context_paths:
        context_parts = context_path.strip("/").split("/")

        if len(context_parts) >= 2:
            # Get the parent path (e.g., /pets from /pets/cats)
            parent_path = "/".join(context_parts[:-1])
            parent_tag = db.query(Tag).filter(Tag.path == f"/{parent_path}").first()
            if parent_tag:
                return parent_tag

        # Also check if first part could be a root
        if len(context_parts) >= 1:
            root_name = context_parts[0]
            root_tag = (
                db.query(Tag)
                .filter(Tag.path == f"/{root_name}", Tag.parent_id.is_(None))
                .first()
            )
            if root_tag:
                return root_tag

    return None


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


# =============================================================================
# Markdown Import & Export
# =============================================================================


@app.post("/import/markdown", response_model=NoteOut)
async def import_markdown_note(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user)  # Uncomment when auth is enforced
):
    from utils.note_utils import import_markdown_to_note

    try:
        content = await file.read()
        md_text = content.decode("utf-8")
        # note = import_markdown_to_note(db, md_text, owner_id=current_user.id)
        note = import_markdown_to_note(db, md_text)
        return note
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Failed to import markdown: {str(e)}"
        )


from fastapi.responses import Response
import zipfile
import io


@app.get("/export/subtree/{subpath:path}")
def export_subtree(subpath: str, db: Session = Depends(get_db)):
    from utils.tag_utils import get_notes_by_subtree
    from utils.markdown_utils import note_to_markdown

    notes = get_notes_by_subtree(db, subpath)

    if not notes:
        raise HTTPException(status_code=404, detail="No notes found in this subtree")

    # Create an in-memory ZIP file
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for note in notes:
            # We convert it to a schema so note_to_markdown works cleanly
            note_out = NoteOut.model_validate(note)
            md_content = note_to_markdown(note_out)
            file_name = f"note_{note.id}.md"
            if note.title:
                # Basic sanitization
                safe_title = "".join(
                    [c for c in note.title if c.isalpha() or c.isdigit() or c == " "]
                ).rstrip()
                if safe_title:
                    file_name = f"{safe_title}_{note.id}.md"

            zip_file.writestr(file_name, md_content)

    # Return ZIP file
    zip_buffer.seek(0)
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=export_{subpath.replace('/', '_')}.zip"
        },
    )


# =============================================================================
# Tag Resolution & Mode Configuration Endpoints
# =============================================================================


@app.post("/tags/resolve")
def resolve_tag(
    input: TagResolveInput,
    db: Session = Depends(get_db),
):
    """
    Resolve a tag name to determine if it needs disambiguation.

    Supports context-aware resolution: if the note already has tags like
    "endocrinologist", adding "doctors" will auto-match "health/doctors".

    Returns:
    - unique_match: Exactly one tag found - frontend can auto-attach
    - multiple_matches: Multiple tags found - frontend should show selection dialog
    - not_found: No tags found - frontend should offer to create new

    Frontend flow:
    1. User types "doctors" and submits (with existing note tags for context)
    2. Backend searches for "doctors" tags
    3. If multiple (health/doctors, kids/doctors), checks existing tags for context
       - If note has "endocrinologist" (under health), auto-selects "health/doctors"
       - Otherwise returns candidates for user to choose
    4. If none, returns suggestion to create new
    """
    from utils.tag_modes import (
        resolve_tag_for_mode,
        get_tag_mode_config,
        TagMode,
    )
    from schemas import TagResolveOutput, TagCandidateOut

    # Determine which mode to use
    mode = input.mode if input.mode else get_tag_mode_config().mode

    # Get existing tags from note if note_id provided
    existing_labels = None
    if input.note_id:
        note = db.query(Note).filter(Note.id == input.note_id).first()
        if note:
            existing_labels = [tag.label for tag in note.tags]

    # Also use explicitly provided existing_tags
    if input.note_tags:
        existing_labels = input.note_tags

    # Resolve the tag with context
    from utils.tag_modes import get_tag_strategy

    strategy = get_tag_strategy(mode)
    result = strategy.resolve_tag(db, input.label, existing_tags=existing_labels)

    # Convert to output schema
    return TagResolveOutput(
        status=result.status,
        can_create=result.can_create,
        tag=(
            TagCandidateOut(**result.selected_tag.to_dict())
            if result.selected_tag
            else None
        ),
        candidates=[TagCandidateOut(**c.to_dict()) for c in result.candidates],
        suggested_parents=[
            TagCandidateOut(**p.to_dict()) for p in result.suggested_parents
        ],
    )


@app.post("/tags/create")
def create_tag(
    input: TagCreateInput,
    db: Session = Depends(get_db),
):
    """
    Create a new tag with optional parent path.

    In path mode: creates hierarchical tags like "health/doctors"
    In flat mode: creates flat tags like "doctors"
    """
    from utils.tag_modes import get_tag_mode_config, get_tag_strategy, TagMode
    from schemas import TagOut, TagStatsOut

    config = get_tag_mode_config()
    mode = input.mode if input.mode else config.mode
    strategy = get_tag_strategy(mode)

    # Determine parent if specified
    parent_tag = None
    if input.parent_path and mode == TagMode.PATH:
        from utils.tag_utils import get_or_create_tag_by_path

        parent_tag = get_or_create_tag_by_path(db, input.parent_path)

    # Create the tag
    tag = strategy.get_or_create_tag(db, input.label, parent=parent_tag)
    db.commit()
    db.refresh(tag)

    return TagOut(
        id=tag.id,
        label=tag.label,
        path=tag.path,
        stats=None,
    )


@app.post("/tags/attach")
def attach_tag_to_note(
    input: TagAttachInput,
    db: Session = Depends(get_db),
):
    """Attach an existing tag to a note."""
    from schemas import NoteOut, TagOut

    note = db.query(Note).filter(Note.id == input.note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    tag = db.query(Tag).filter(Tag.id == input.tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    if tag not in note.tags:
        note.tags.append(tag)
        db.commit()
        db.refresh(note)

    # Build the response manually to avoid validation issues
    return NoteOut(
        id=note.id,
        title=note.title,
        content=note.content,
        media_path=note.media_path,
        media_type=note.media_type,
        link=note.link,
        created_at=note.created_at,
        updated_at=note.updated_at,
        tags=[
            TagOut(id=t.id, label=t.label, path=t.path, stats=None) for t in note.tags
        ],
    )


@app.get("/tags/mode")
def get_current_tag_mode():
    """Get the current tag mode configuration."""
    from utils.tag_modes import get_tag_mode_config

    config = get_tag_mode_config()
    return {
        "mode": config.mode.value,
        "disambiguation_enabled": config.disambiguation_enabled,
        "auto_create_tags": config.auto_create_tags,
    }


@app.post("/tags/mode")
def set_tag_mode(
    mode: str,
    disambiguation_enabled: bool = True,
    auto_create_tags: bool = True,
):
    """Update tag mode configuration."""
    from utils.tag_modes import (
        set_tag_mode_config,
        TagModeConfig,
        TagMode,
    )

    tag_mode = TagMode.PATH if mode == "path" else TagMode.FLAT

    set_tag_mode_config(
        TagModeConfig(
            mode=tag_mode,
            disambiguation_enabled=disambiguation_enabled,
            auto_create_tags=auto_create_tags,
        )
    )

    return {"mode": mode, "status": "updated"}


# =============================================================================
# LLM Export Endpoints
# =============================================================================


@app.get("/export/llm")
def export_for_llm(db: Session = Depends(get_db)):
    """
    Export all notes and tags in a compact format for LLM analysis.

    Returns JSON that can be sent to an LLM to suggest hierarchy reorganization.
    """
    from utils.llm_utils import export_all_for_llm

    data = export_all_for_llm(db)
    return data.to_dict()


@app.post("/import/llm/suggestions")
def apply_llm_suggestions(
    suggestions: dict,
    dry_run: bool = True,
    db: Session = Depends(get_db),
):
    """
    Apply LLM-generated hierarchy suggestions.

    The suggestions dict should contain:
    - tag_mappings: list of {old_tag_id, new_path, action}
    - new_root_categories: optional list of new categories
    """
    from utils.llm_utils import HierarchySuggestion, apply_hierarchy_suggestions

    hierarchy_suggestion = HierarchySuggestion.from_dict(suggestions)
    result = apply_hierarchy_suggestions(db, hierarchy_suggestion, dry_run=dry_run)

    return result


# =============================================================================
# Tag Query Endpoints
# =============================================================================


@app.get("/tags/search")
def search_tags(
    q: str,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    """Search tags by name (for autocomplete)."""
    from utils.tag_utils import tag_processor

    normalized = tag_processor.normalize(q)

    tags = db.query(Tag).filter(Tag.label.ilike(f"%{normalized}%")).limit(limit).all()

    return [{"id": t.id, "label": t.label, "path": t.path} for t in tags]


@app.get("/tags/subtree/{root_path:path}")
def get_tags_in_subtree(
    root_path: str,
    db: Session = Depends(get_db),
):
    """Get all tags in a subtree."""
    from utils.llm_utils import query_tags_in_subtree

    tags = query_tags_in_subtree(db, root_path)

    return [{"id": t.id, "label": t.label, "path": t.path} for t in tags]


@app.get("/tags/hierarchy")
def get_tag_hierarchy(db: Session = Depends(get_db)):
    """Get complete tag hierarchy as nested dict."""
    from utils.llm_utils import get_tag_hierarchy_tree

    return get_tag_hierarchy_tree(db)
