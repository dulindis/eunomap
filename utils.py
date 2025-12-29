import json
import re
import shutil
import unicodedata
from pathlib import Path

import inflect
from fastapi import UploadFile
from sqlalchemy.orm import Session

import models
from models import Tag

# =============================================================================
# Constants
# =============================================================================

# Inflect engine for pluralization/singularization
_inflect = inflect.engine()

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
    "covid-19",
    "tips",
    "tricks",
    "others",
    "tips_and_tricks",
}

# Explicit aliases for things that should unify
ALIASES = {
    "ai/ml": "ai_ml",
    "c#": "csharp",
    "node.js": "node_js",
    "fruit_&_vegetables": "fruit_and_vegetables",
    "meat_&_seafood": "meat_and_seafood",
}

# Sample users for testing/demo purposes
SAMPLE_USERS = [
    {"username": "alice123", "email": "alice@example.com", "password_hash": "hash1"},
    {"username": "bobby_trax", "email": "bob@example.com", "password_hash": "hash2"},
]

# =============================================================================
# Tag Normalization
# =============================================================================


def normalize(name: str) -> str:
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
        name: Raw tag name

    Returns:
        Normalized tag name

    Examples:
        >>> normalize("Cats & Dogs")
        'cat_and_dog'
        >>> normalize("AI/ML")
        'ai_ml'
        >>> normalize("Node.js")
        'node_js'
    """
    if not name:
        return ""

    # Unicode normalization
    name = unicodedata.normalize("NFKC", name)
    name = name.strip().lower()

    # Replace special characters
    name = name.replace("&", " and ")
    name = name.replace("/", "_")

    # Remove non-word characters (keep underscores and hyphens)
    name = re.sub(r"[^\w\s-]", "", name)

    # Convert spaces and hyphens to underscores
    name = re.sub(r"[\s\-]+", "_", name)

    # Remove duplicate underscores
    name = re.sub(r"_+", "_", name)

    # Apply aliases
    if name in ALIASES:
        return ALIASES[name]

    # Singularize last word if applicable
    parts = name.split("_")
    last = parts[-1]

    if last not in DO_NOT_SINGULARIZE:
        singular = _inflect.singular_noun(last)
        if singular:
            parts[-1] = singular

    name = "_".join(parts)

    return name


# =============================================================================
# Hierarchy Management
# =============================================================================


def load_hierarchy(file_path: str = "hierarchy.json") -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


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
        if s.lower().startswith(current_input.lower())
        and s.lower() not in [t.lower() for t in selected_tags]
    ]


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
