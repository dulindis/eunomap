import json

from sqlalchemy.orm import Session

from utils.tag_utils import get_or_create_tag, tag_processor


###
# Load hierarchy from file
def load_hierarchy(file_path: str = "hierarchy.json") -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        return normalize_hierarchy(json.load(f), 3)


# Normalize hierarchy json
def normalize_hierarchy(node, max_depth):
    # print(f"node={node} max_depth={max_depth}")

    if max_depth == 0:
        raise RuntimeError("Max depth reached")

    next_max_depth = max_depth - 1

    def normalize_dict(node):
        return {k: normalize_hierarchy(v, next_max_depth) for (k, v) in node.items()}

    if isinstance(node, dict):
        return normalize_dict(node)
    elif isinstance(node, str):
        return {node: {}}
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
            elif isinstance(x, dict):
                dst.update(normalize_dict(x))
                i += 1
            else:
                raise RuntimeError("Syntax error B")
        return dst
    else:
        raise RuntimeError("Syntax error C")


def compress_hierarchy(node):
    assert isinstance(node, dict)
    non_empty = [v for v in node.values() if len(v) != 0]
    if len(non_empty) == 0:
        return list(node.keys())
    else:
        return {k: compress_hierarchy(v) for (k, v) in node.items()}


### STREAMLIT HIERARCHY UTILS
# Flatten tag list for Streamlit
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
# Tag resolution algorithm (core logic)
# =============================================================================

from collections import defaultdict
from models import Tag


def resolve_tags(db, labels: list[str]) -> list[Tag]:
    """
    Resolve user-provided labels into concrete Tag nodes.
    Raises AmbiguousTagError if resolution is not unique.
    """

    # 1. Fetch all candidates
    candidates_by_label = {
        label: db.query(Tag).filter(Tag.label == label).all() for label in labels
    }

    # If any label has no candidates → create root tag
    for label, candidates in candidates_by_label.items():
        if not candidates:
            candidates_by_label[label] = [get_or_create_tag(db, label, parent=None)]

    # 2. Flatten all candidates
    all_candidates = [t for tags in candidates_by_label.values() for t in tags]

    # 3. Score candidates
    scores = defaultdict(int)

    for tag in all_candidates:
        for other in all_candidates:
            if tag.id == other.id:
                continue
            scores[tag] += hierarchy_distance(tag, other)

    # 4. Pick lowest score
    min_score = min(scores.values())
    best = [tag for tag, score in scores.items() if score == min_score]

    if len(best) > 1:
        raise AmbiguousTagError(best)

    return best


# Hierarchy distance function
def hierarchy_distance(a: Tag, b: Tag) -> int:
    """
    Distance based on path divergence.
    Lower = closer in hierarchy.
    """
    a_parts = a.path.strip("/").split("/")
    b_parts = b.path.strip("/").split("/")

    common = 0
    for x, y in zip(a_parts, b_parts):
        if x == y:
            common += 1
        else:
            break

    return (len(a_parts) - common) + (len(b_parts) - common)


# Custom exception
class AmbiguousTagError(Exception):
    def __init__(self, candidates):
        self.candidates = candidates
