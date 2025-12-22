import json
import models
from sqlalchemy.orm import Session


# ----------------------------
# Load hierarchy JSON
# ----------------------------
def load_hierarchy(file_path="hierarchy.json"):
    """Load the JSON hierarchy from a file."""
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
    """
    Return a list of suggestions based on last selected tag and current input.
    This is optional for flat autocomplete; useful for hierarchical scenarios.
    """
    if selected_tags:
        last_tag = selected_tags[-1].lower()
        suggestions = flat_mapping.get(last_tag, list(flat_mapping.keys()))
    else:
        suggestions = list(flat_mapping.keys())

    # Filter by current input and remove already selected
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
    """Trim whitespace and force lowercase."""
    return name.strip().lower()


# ----------------------------
# Efficient Recursive Tag Insertion
# ----------------------------
# def add_tags(node, db: Session, parent=None):
#     """
#     Recursively add tags from a hierarchy dict to the database.
#     Commits once at the end for efficiency.
#     """
#     # Cache existing tags to avoid duplicate queries
#     existing_tags = {t.name.lower(): t for t in db.query(models.Tag).all()}

#     def _add_node(sub_node, parent_tag=None):
#         if isinstance(sub_node, dict):
#             for key, value in sub_node.items():
#                 tag_lower = normalize(key)

#                 tag = existing_tags.get(tag_lower)
#                 if not tag:
#                     tag = models.Tag(name=tag_name, parent=parent_tag)
#                     db.add(tag)
#                     existing_tags[tag_lower] = tag  # add to cache

#                 # Recursively add children
#                 if isinstance(value, dict):
#                     _add_node(value, parent_tag=tag)
#                 elif isinstance(value, list):
#                     for child_name in value:
#                         child_lower = child_name.lower().strip()
#                         child_tag = existing_tags.get(child_lower)
#                         if not child_tag:
#                             child_tag = models.Tag(name=child_name, parent=tag)
#                             db.add(child_tag)
#                             existing_tags[child_lower] = child_tag
#         elif isinstance(sub_node, list):
#             for child_name in sub_node:
#                 child_lower = child_name.lower().strip()
#                 child_tag = existing_tags.get(child_lower)
#                 if not child_tag:
#                     child_tag = models.Tag(name=child_name, parent=parent_tag)
#                     db.add(child_tag)
#                     existing_tags[child_lower] = child_tag

#     _add_node(node, parent_tag=parent)
#     db.commit()  # single commit at the end


def add_tags(node, db: Session, parent=None):
    """
    Recursively add tags from a hierarchy dict to the database.
    - lowercase
    - trimmed
    - single commit
    """
    existing_tags = {t.name: t for t in db.query(models.Tag).all()}

    def _add_node(sub_node, parent_tag=None):
        if isinstance(sub_node, dict):
            for key, value in sub_node.items():
                name = normalize(key)

                tag = existing_tags.get(name)
                if not tag:
                    tag = models.Tag(name=name, parent=parent_tag)
                    db.add(tag)
                    existing_tags[name] = tag

                if isinstance(value, dict):
                    _add_node(value, parent_tag=tag)
                elif isinstance(value, list):
                    for child in value:
                        child_name = normalize(child)
                        child_tag = existing_tags.get(child_name)
                        if not child_tag:
                            child_tag = models.Tag(name=child_name, parent=tag)
                            db.add(child_tag)
                            existing_tags[child_name] = child_tag

        elif isinstance(sub_node, list):
            for child in sub_node:
                child_name = normalize(child)
                if child_name not in existing_tags:
                    child_tag = models.Tag(name=child_name, parent=parent_tag)
                    db.add(child_tag)
                    existing_tags[child_name] = child_tag

    _add_node(node, parent_tag=parent)
    db.commit()
