import json
import re
import shutil
import unicodedata
from pathlib import Path
from passlib.context import CryptContext
from typing import List

import inflect
from fastapi import UploadFile
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer, util


import models
from models import Tag

# =============================================================================
# Constants
# =============================================================================

# Inflect engine for pluralization/singularization
# _inflect = inflect.engine()

# Load a small embedding model once
# embed_model = SentenceTransformer("all-MiniLM-L6-v2")  # fast, small

DO_NOT_SINGULARIZE = {
    "news",
    "series",
    "analytics",
    "music",
    "fitness",
    "wellness",
    "mindfulness",
    "data",
    "children",
    "development",
    "design",
    "ai",
    "ml",
    "adhd",
    "hiv",
    "aids",
    # "covid-19",
    "tips",
    "tricks",
    "others",
    "tips_and_tricks",
    "nodejs",
    "kids",  # ?? child
}

# Explicit aliases for things that should unify
ALIASES = {
    # "ai/ml": "ai_ml",
    # "c#": "csharp",
    # "node.js": "node_js",
    # "fruit_&_vegetables": "fruit_and_vegetables",
    # "meat_&_seafood": "meat_and_seafood",
    # "r&d": "r_and_d",
}

# Sample users for testing/demo purposes
SAMPLE_USERS = [
    {"username": "alice123", "email": "alice@example.com", "password_hash": "hash1"},
    {"username": "bobby_trax", "email": "bob@example.com", "password_hash": "hash2"},
]

# Maximum number of tags to suggest (for semantic search)
MAX_TAGS = 4

# =============================================================================
# Tag Normalization
# =============================================================================


# v2
def normalize(text: str) -> str:
    """
    Normalize a tag name while preserving meaningful special characters (#, +, &).

    Process:
    1. Unicode normalization (NFKC)
    2. Lowercase
    3. Apply aliases first
    4. Remove non-word characters except underscores, hyphens, #, +, &
    5. Collapse spaces to underscores
    6. Singularize the last word if applicable

    Examples:
        >>> normalize("C++ programming")
        'c++_programming'
        >>> normalize("Mac&CHEESE")
        'mac&cheese'
        >>> normalize("co--op")
        'co-op'
        >>> normalize("COVID-19")
        'covid-19'
    """
    if not text:
        return ""

    # 1️⃣ Unicode normalization and lowercase
    text = unicodedata.normalize("NFKC", text).strip().lower()

    # 2️⃣ Apply aliases first
    if text in ALIASES:
        return ALIASES[text]

    # # 3️⃣ Remove unwanted punctuation but keep #, +, &, hyphen, underscore, and backslash
    # text = re.sub(r"[^\w\s#\+&\-_\\]", "", text)
    # 3️⃣ Keep only: letters, digits, spaces, underscores, hyphens, #, +, &, /
    # Note: Must escape + and & inside character class, or place them carefully
    # text = re.sub(r"[^a-z0-9\s_\-#+&]", "", text)
    text = re.sub(r"[^a-z0-9\s_\-#\+&/]", "", text)

    # 4️⃣ Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)

    # 5️⃣ Convert spaces to underscores (hyphens and special chars preserved)
    text = text.replace(" ", "_")

    # Remove duplicate underscores
    text = re.sub(r"_+", "_", text)

    # Remove double hyphens
    text = re.sub(r"-+", "-", text)

    # 6️⃣ Singularize last word if allowed and purely alphabetic
    parts = text.split("_")
    last = parts[-1]

    if last not in DO_NOT_SINGULARIZE and last.isalpha():
        singular = _inflect.singular_noun(last)
        if singular:
            parts[-1] = singular

    text = "_".join(parts)

    return text

    # v1
    # def normalize(text: str) -> str:
    """
    Normalize a tag name to a consistent format.

    Process:
    1. Unicode normalization (NFKC)
    2. Convert to lowercase
    3. Replace special characters (&, /) with standard forms
    4. Remove non-word characters except underscores and hyphens
    5. Convert spaces and hyphens to underscores
    6. Apply aliases
    7. Singularize the last word (unless in DO_NOT_SINGULARIZE)

    Args:
        name: Raw tag text

    Returns:
        Normalized tag text

    Examples:
        >>> normalize("Cats & Dogs")
        'cat_and_dog'
        >>> normalize("AI/ML")
        'ai_ml'
        >>> normalize("Node.js")
        'node_js'
    """
    if not text:
        return ""

    # Unicode normalization
    text = unicodedata.normalize("NFKC", text)
    text = text.strip().lower()

    # Replace special characters
    text = text.replace("&", " and ")
    text = text.replace("/", "_")

    # Apply aliases
    if text in ALIASES:
        return ALIASES[text]

    # Remove non-word characters (keep underscores and hyphens)
    text = re.sub(r"[^\w\s-]", "", text)

    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)

    # 6️⃣ Convert spaces to underscores (but preserve hyphens)
    text = text.replace(" ", "_")

    # Remove duplicate underscores
    text = re.sub(r"_+", "_", text)

    # Convert spaces and hyphens to underscores
    text = re.sub(r"[\s]+", "_", text)
    # # Convert spaces and hyphens to underscores
    # text = re.sub(r"[\s\-]+", "_", text)

    # Singularize last word if applicable
    parts = text.split("_")
    last = parts[-1]

    if last not in DO_NOT_SINGULARIZE and last.isalpha():  # only alphabetic words
        singular = _inflect.singular_noun(last)
        if singular:
            parts[-1] = singular

    text = "_".join(parts)

    return text


# =============================================================================
# Hierarchy Management
# =============================================================================


# def load_hierarchy(file_path: str = "hierarchy.json") -> dict:
#     with open(file_path, "r", encoding="utf-8") as f:
#         return json.load(f)


def normalize_hierarchy(node, max_depth):
    print(f"node={node} max_depth={max_depth}")

    if max_depth == 0:
        raise RuntimeError("Max depth reached")

    next_max_depth = max_depth - 1

    if isinstance(node, dict):
        return {k: normalize_hierarchy(v, next_max_depth) for (k, v) in node.items()}
    elif isinstance(node, list):
        n = len(node)
        i = 0
        dst = {}
        while i < n:
            x = node[i]
            if isinstance(x, str):
                if i < n - 1 and (
                    isinstance(node[i + 1], list) or isinstance(node[i + 1], dict)
                ):
                    dst[x] = normalize_hierarchy(node[i + 1], next_max_depth)
                    i += 2
                else:
                    dst[x] = {}
                    i += 1
            else:
                raise RuntimeError("Syntax error B")
        return dst
    else:
        raise RuntimeError("Syntax error C")


def load_hierarchy(file_path: str = "hierarchy.json") -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        return normalize_hierarchy(json.load(f), 3)


def flatten_all_tags(node) -> list[str]:
    """
     Recursively flatten a hierarchy into a list of all tag names.

    Includes both category names (dict keys) and leaf tags (list items).

    Args:
        node: Dictionary or list representing part of the hierarchy

    Returns:
        Flat list of all tag names in the hierarchy

    Example:
        >>> hierarchy = {"Health": {"Fitness": ["Yoga", "Running"]}}
        >>> flatten_all_tags(hierarchy)
        ['Health', 'Fitness', 'Yoga', 'Running']
    """
    flat_list = []

    if isinstance(node, dict):
        for k, v in node.items():
            flat_list.append(k)  # include the category itself
            flat_list.extend(flatten_all_tags(v))
    elif isinstance(node, list):
        flat_list.extend(node)
    return flat_list


def flatten_hierarchy(topic_key: str, hierarchy: dict) -> list[str]:
    """
    Flatten a specific branch of the hierarchy.

    Args:
        topic_key: Key to look up in the hierarchy
        hierarchy: Full hierarchy dictionary

    Returns:
        Flat list of tags under the specified topic
    """
    subsections = hierarchy.get(topic_key, [])
    flat_list = []

    if isinstance(subsections, dict):
        for subkey, value in subsections.items():
            if isinstance(value, list):
                flat_list.extend(value)
            elif isinstance(value, dict):
                # Recursively flatten deeper
                flat_list.extend(flatten_hierarchy(subkey, {subkey: value}))
    elif isinstance(subsections, list):
        flat_list.extend(subsections)

    return flat_list


def build_flat_mapping(node) -> dict[str, list]:
    """
    Build a parent->children mapping from the hierarchy.

    Useful for context-aware hierarchical autocomplete suggestions.

    Args:
        node: Dictionary representing the hierarchy

    Returns:
        Dictionary mapping parent tags to their immediate children

    Example:
        >>> hierarchy = {"Health": {"Fitness": ["Yoga", "Running"]}}
        >>> build_flat_mapping(hierarchy)
        {'health': ['Fitness'], 'fitness': ['Yoga', 'Running']}
    """
    mapping = {}

    if isinstance(node, dict):
        for k, v in node.items():
            key_lower = k.lower()

            if isinstance(v, dict):
                mapping[key_lower] = list(v.keys())
                mapping.update(build_flat_mapping(v))
            elif isinstance(v, list):
                mapping[key_lower] = v

    return mapping


# =============================================================================
# Tag Database Operations
# =============================================================================


def get_or_create_tag(
    db: Session, name: str, parent: Tag | None = None, auto_others: bool = True
) -> Tag:
    """
    Get an existing tag or create a new one with optional parent relationship.

    If the tag exists, adds the parent relationship if it doesn't already exist.
    If the tag is new and no parent is specified, assigns it to "others" category
    (unless auto_others=False or the tag itself is "others").

    Args:
        db: Database session
        name: Tag name (will be normalized)
        parent: Optional parent tag
        auto_others: If True and no parent, assign to "others" category

    Returns:
        Tag object (existing or newly created)
    """
    name = normalize(name)

    tag = db.query(Tag).filter_by(name=name).first()

    if tag:
        # Tag exists - check if we need to add a new parent relationship
        if parent and parent not in tag.parents:
            tag.parents.append(parent)
            db.flush()
        elif auto_others and name != "others":
            # Check if 'others' is already a parent
            others_name = normalize("others")
            others_tag = db.query(Tag).filter_by(name=others_name).first()
            if others_tag and others_tag not in tag.parents:
                tag.parents.append(others_tag)
                db.flush()
        return tag

    # Tag doesn't exist - create it
    tag = Tag(name=name)
    db.add(tag)
    db.flush()

    # Add parent relationship
    if parent:
        tag.parents.append(parent)
        db.flush()
    elif auto_others and name != "others":
        others_name = normalize("others")
        others_tag = db.query(Tag).filter_by(name=others_name).first()
        if not others_tag:
            others_tag = Tag(name=others_name)
            db.add(others_tag)
            db.flush()
        tag.parents.append(others_tag)
        db.flush()

    db.refresh(tag)
    return tag


def add_tags(hierarchy, parent_tag: Tag | None = None, db: Session = None) -> None:
    """
    Recursively add tags from a hierarchy structure to the database.

    Processes both dictionary (categories with subcategories) and list
    (flat lists of tags) structures.

    Args:
        hierarchy: Dictionary or list representing the hierarchy
        parent_tag: Optional parent tag for the current level
        db: Database session
    """
    if isinstance(hierarchy, dict):
        for k, v in hierarchy.items():
            tag = get_or_create_tag(db, k, parent=parent_tag, auto_others=False)
            add_tags(v, parent_tag=tag, db=db)

    elif isinstance(hierarchy, list):
        for item in hierarchy:
            # _add_node(item, parent_tag=parent_tag, db=db, auto_others=False)
            get_or_create_tag(db, item, parent=parent_tag, auto_others=False)


# =============================================================================
# User Database Operations
# =============================================================================


def add_user(db, username, email=None, password_hash=None, is_active=True):
    """
    Add a single user to the database.

    Args:
        db: SQLAlchemy Session
        username: str
        email: str (optional)
        password_hash: str
        is_active: bool

    Returns:
        User: newly created User object
    """
    from models import User

    user = User(
        username=username, email=email, password_hash=password_hash, is_active=is_active
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def add_users(users: list, db: Session):
    """
    Add multiple users to the database.

    Args:
        db: SQLAlchemy Session
        users: List of dicts with keys username, email, password_hash, is_active

    Returns:
        List[User]: List of created User objects
    """
    created_users = []
    for u in users:
        user = add_user(
            db,
            username=u.get("username"),
            email=u.get("email"),
            password_hash=u.get("password_hash"),
            is_active=u.get("is_active", True),
        )
        created_users.append(user)
    return created_users


# =============================================================================
# Autocomplete Suggestions
# =============================================================================


def get_suggestions(selected_tags, current_input, flat_mapping) -> list[str]:
    if selected_tags:
        last_tag = selected_tags[-1].lower()
        suggestions = flat_mapping.get(last_tag, list(flat_mapping.keys()))
    else:
        suggestions = list(flat_mapping.keys())

    return [
        s
        for s in suggestions
        if s.lower().startswith(
            current_input.lower()
        )  # This will never work for transcriptions.
        and s.lower() not in [t.lower() for t in selected_tags]
    ]


def suggest_tags_from_text(
    text: str,
    db: Session,
    selected_tags: list[str] | None = None,
) -> list[str]:

    if not text:
        return ["others"]
    # Normalize selected tags
    selected_norm = {normalize(t) for t in (selected_tags or [])}

    text_norm = normalize(text)
    tags = db.query(Tag).all()
    # for t in db.query(Tag).all():
    #     print("TAGI TESTOWE:", t.name)

    matches = find_exact_tag_matches(
        text_norm=text_norm,
        tags=tags,
        selected_norm=selected_norm,
    )

    if not matches:
        return ["others"]

    return sorted(
        matches,
        key=lambda t: text_norm.count(normalize(t)),
        reverse=True,
    )


# working
# def suggest_tags_from_text_semantic(
#     text: str,
#     db: Session,
#     selected_tags: List[str] | None = None,
#     threshold: float = 0.6,
# ) -> List[str]:
#     """
#     Suggests tags for a given text using exact match and semantic similarity.

#     Args:
#         text: Input text to extract tags from.
#         db: SQLAlchemy database session.
#         selected_tags: Already selected tags to exclude from suggestions.
#         threshold: Minimum similarity score for semantic suggestions.

#     Returns:
#         List of suggested tag names (max MAX_TAGS). If none found, returns ["others"].
#     """
#     if not text:
#         return ["others"]

#     selected_norm = {normalize(t) for t in (selected_tags or [])}
#     text_norm = normalize(text)

#     # Fetch all tags
#     tags = db.query(Tag).all()
#     suggestions = []

#     # Exact matches
#     exact_matches = []
#     remaining_tags_list = []

#     for tag in tags:
#         tag_norm = normalize(tag.name)
#         if tag_norm in selected_norm:
#             continue

#         pattern = rf"(?:^|_){re.escape(tag_norm)}(?:_|$)"
#         if re.search(pattern, text_norm):
#             exact_matches.append(tag.name)
#         else:
#             remaining_tags_list.append(tag)

#     suggestions.extend(exact_matches[:MAX_TAGS])

#     # # Stop if we already reached max tags
#     if len(suggestions) >= MAX_TAGS:
#         return suggestions[:MAX_TAGS]

#     # Semantic similarity for remaining tags
#     if remaining_tags_list and embed_model:
#         tag_texts = [tag.name for tag in remaining_tags_list]
#         tag_norms = [normalize(tag.name) for tag in remaining_tags_list]

#         # Compute embeddings
#         text_emb = embed_model.encode(text_norm, convert_to_tensor=True)
#         tag_embs = embed_model.encode(tag_texts, convert_to_tensor=True)
#         sims = util.cos_sim(text_emb, tag_embs)[0]

#         # Collect tags above threshold
#         sem_suggestions = [
#             tag_texts[i]
#             for i, sim_score in enumerate(sims)
#             if sim_score >= threshold and tag_norms[i] not in selected_norm
#         ]

#         # Sort by similarity
#         sem_suggestions_sorted = [
#             tag
#             for _, tag in sorted(
#                 zip(sims.tolist(), sem_suggestions), key=lambda x: x[0], reverse=True
#             )
#         ]

#         # Add remaining tags up to MAX_TAGS
#         for tag in sem_suggestions_sorted:
#             if len(suggestions) >= MAX_TAGS:
#                 break
#             suggestions.append(tag)

#     # Fallback to "others"
#     if not suggestions:
#         suggestions.append("others")

#     return suggestions


def find_exact_tag_matches(
    text_norm: str,
    tags: list[Tag],
    selected_norm: set[str],
) -> tuple[list[str], list[Tag]]:
    """
    Finds exact tag matches in text.

    Returns:
        - list of matched tag names
        - list of remaining Tag objects (not matched)
    """
    matches: list[str] = []

    for tag in tags:
        tag_norm = normalize(tag.name)

        if tag_norm in selected_norm:
            continue

        if tag_norm in text_norm:
            matches.append(tag.name)

    return matches


def suggest_tags_from_text_semantic(
    text: str,
    db: Session,
    selected_tags: list[str] | None = None,
    threshold: float = 0.6,
) -> list[str]:
    if not text:
        return ["others"]

    text_norm = normalize(text)
    selected_norm = {normalize(t) for t in (selected_tags or [])}

    tags = db.query(Tag).all()
    suggestions: list[str] = []

    # 1️⃣ Exact matches
    exact_matches = find_exact_tag_matches(
        text_norm=text_norm,
        tags=tags,
        selected_norm=selected_norm,
    )
    exact_matches_sorted = sorted(
        exact_matches,
        key=lambda t: text_norm.count(normalize(t)),
        reverse=True,
    )
    suggestions.extend(exact_matches_sorted[:MAX_TAGS])

    if len(suggestions) >= MAX_TAGS:
        return suggestions[:MAX_TAGS]

    matched_norms = {normalize(t) for t in exact_matches}
    remaining_tags = [
        tag
        for tag in tags
        if normalize(tag.name) not in matched_norms
        and normalize(tag.name) not in selected_norm
    ]

    # 2️⃣ Semantic matches
    if remaining_tags and embed_model:
        tag_texts = [tag.name for tag in remaining_tags]
        tag_norms = [normalize(tag.name) for tag in remaining_tags]

        text_emb = embed_model.encode(text_norm, convert_to_tensor=True)
        tag_embs = embed_model.encode(tag_texts, convert_to_tensor=True)
        sims = util.cos_sim(text_emb, tag_embs)[0]

        sem_candidates = [
            (sims[i].item(), tag_texts[i])
            for i in range(len(tag_texts))
            if sims[i] >= threshold and tag_norms[i] not in selected_norm
        ]

        sem_candidates.sort(key=lambda x: x[0], reverse=True)
        # TODO: make sure that the synonym doesnt exist in extact matches
        for _, tag in sem_candidates:
            if len(suggestions) >= MAX_TAGS:
                break
            suggestions.append(tag)

    return suggestions or ["others"]


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


# =============================================================================
# Password Hashing Helper
# =============================================================================
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
