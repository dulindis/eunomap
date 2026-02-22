from typing import List, Dict, Optional, Any
from . import api_client

def resolve_tag(label: str, note_tags: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """
    Resolve a tag and return result.
    Uses existing /tags/resolve endpoint with normalization.
    """
    payload = {"label": label, "note_tags": note_tags or []}
    response = api_client.post("/tags/resolve", json=payload)
    if response.status_code == 200:
        return response.json()
    return None

def create_tag(label: str) -> Optional[Dict[str, Any]]:
    payload = {"label": label}
    response = api_client.post("/tags/create", json=payload)
    if response.status_code == 200:
        return response.json()
    return None

def attach_tag(note_id: int, tag_id: int) -> bool:
    payload = {"note_id": note_id, "tag_id": tag_id}
    response = api_client.post("/tags/attach", json=payload)
    return response.status_code == 200

def search_tags(query: str) -> List[Dict[str, Any]]:
    response = api_client.get(f"/tags/search", params={"q": query})
    if response.status_code == 200:
        return response.json()
    return []

def get_hierarchy() -> Dict[str, Any]:
    response = api_client.get("/tags/hierarchy")
    if response.status_code == 200:
        return response.json()
    return {}
