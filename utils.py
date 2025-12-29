import json
import shutil

from fastapi import UploadFile
import models
from sqlalchemy.orm import Session
import re
import inflect
import unicodedata
from models import Tag
from pathlib import Path


# ----------------------------
# Load hierarchy JSON
# ----------------------------
def load_hierarchy(file_path="hierarchy.json"):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ----------------------------
# Flatten hierarchy into a flat list of all tags
# ----------------------------
def flatten_all_tags(node):
    """
    Recursively walk a dict/list hierarchy and return a flat list of strings.
    Includes both category names and leaf tags.
    """
    flat_list = []
    if isinstance(node, dict):
        for k, v in node.items():
            flat_list.append(k)  # include the category itself
            flat_list.extend(flatten_all_tags(v))
    elif isinstance(node, list):
        flat_list.extend(node)
    return flat_list


# ----------------------------
# Build flat parent->children mapping (for future hierarchical autocomplete)
# ----------------------------
def build_flat_mapping(node):
    """
    Returns a dict mapping parent->children (keys and their immediate subkeys or leaf items).
    Useful if you want context-aware hierarchical suggestions later.
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


# ----------------------------
# Get suggestions for hierarchical autocomplete (future use)
# ----------------------------
def get_suggestions(selected_tags, current_input, flat_mapping):
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


def flatten_hierarchy(topic_key, hierarchy):
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


def normalize(name: str) -> str:
    if not name:
        return ""
    name = unicodedata.normalize("NFKC", name)
    name = name.strip().lower()
    name = name.replace("&", " and ")
    name = name.replace("/", "_")
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s\-]+", "_", name)
    name = re.sub(r"_+", "_", name)

    if name in ALIASES:
        return ALIASES[name]

    parts = name.split("_")
    last = parts[-1]

    if last not in DO_NOT_SINGULARIZE:
        singular = _inflect.singular_noun(last)
        if singular:
            parts[-1] = singular

    name = "_".join(parts)

    return name


def _add_node(name, parent_tag=None, db=None, auto_others=True):
    name = normalize(name)
    tag = db.query(models.Tag).filter_by(name=name).first()

    if not tag:
        tag = models.Tag(name=name)
        if parent_tag:
            tag.parents.append(parent_tag)
        elif auto_others:
            # fetch or create "others" tag
            others_tag = db.query(models.Tag).filter_by(name="others").first()
            if not others_tag:
                others_tag = models.Tag(name="others")
                db.add(others_tag)
                db.flush()
            tag.parents.append(others_tag)
        db.add(tag)
        db.flush()  # żeby mieć tag.id jeśli potrzebne
    return tag


def get_or_create_tag(
    db: Session, name: str, parent: Tag | None = None, auto_others: bool = True
) -> Tag:
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


def add_tags(hierarchy, parent_tag: Tag | None = None, db: Session = None):
    if isinstance(hierarchy, dict):
        for k, v in hierarchy.items():
            # tag = _add_node(k, parent_tag=parent_tag, db=db, auto_others=False)
            tag = get_or_create_tag(db, k, parent=parent_tag, auto_others=False)

            add_tags(v, parent_tag=tag, db=db)
    elif isinstance(hierarchy, list):
        for item in hierarchy:
            # _add_node(item, parent_tag=parent_tag, db=db, auto_others=False)
            get_or_create_tag(db, item, parent=parent_tag, auto_others=False)


def save_upload(file: UploadFile, note_id: int, upload_dir: Path) -> str:
    ext = Path(file.filename).suffix.lower()
    safe_filename = f"note_{note_id}{ext}"
    file_path = upload_dir / safe_filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return f"static/uploads/{safe_filename}"
