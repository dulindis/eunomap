from typing import Dict, Any, List

def flatten_hierarchy(hierarchy: Dict[str, Any]) -> List[str]:
    """Recursively flattens a hierarchy dictionary to return only the tag keys."""
    tags = []
    if not isinstance(hierarchy, dict):
        return tags
    
    for key, val in hierarchy.items():
        if key != "others":  # omit or keep depending on business logic, kept here to be safe
            pass
        tags.append(key)
        if isinstance(val, dict):
            tags.extend(flatten_hierarchy(val))
    return sorted(list(set(tags)))
