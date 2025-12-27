import json
import models
from sqlalchemy.orm import Session
import re


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


def normalize(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"_+", "_", name)
    return name


def _add_node(name, parent_tag=None, db=None):
    # Sprawdź, czy tag istnieje
    name = normalize(name)
    tag = db.query(models.Tag).filter_by(name=name).first()
    # if not tag:
    #     tag = models.Tag(name=name)
    #     # Assign parent "Others" if no parent provided
    #     if parent_tag is None:
    #         others_tag = db.query(models.Tag).filter_by(name="others").first()
    #         if not others_tag:
    #             others_tag = models.Tag(name="others")
    #             db.add(others_tag)
    #             db.flush()
    #         tag.parents.append(others_tag)
    #     else:
    #         tag.parents.append(parent_tag)
    #     db.add(tag)
    #     db.flush()
    if not tag:
        tag = models.Tag(name=name)
        if parent_tag:
            tag.parents.append(parent_tag)  # <-- dodanie relacji parent-child
        db.add(tag)
        db.flush()  # żeby mieć tag.id jeśli potrzebne
    return tag


def add_tags(hierarchy, parent_tag=None, db=None):
    if isinstance(hierarchy, dict):
        for k, v in hierarchy.items():
            tag = _add_node(k, parent_tag=parent_tag, db=db)
            add_tags(v, parent_tag=tag, db=db)
    elif isinstance(hierarchy, list):
        for item in hierarchy:
            _add_node(item, parent_tag=parent_tag, db=db)
