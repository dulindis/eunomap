from typing import Dict, Any, Tuple
from . import api_client

def create_note(content: str, tags: str, file=None) -> Tuple[bool, Any]:
    """
    Creates a new note. 
    Returns (success_boolean, response_data_or_error_message).
    """
    data = {"content": content, "tags": tags}
    
    files = None
    if file:
        files = {"file": (file.name, file, "multipart/form-data")}
        
    response = api_client.post("/notes/", data=data, files=files)
    
    if response.status_code == 200:
        return True, response.json()
    else:
        return False, response.text

def generate_topic_markdown(topic_path: str) -> Tuple[bool, Any]:
    """
    Generates markdown for a given topic path.
    """
    response = api_client.get(f"/generate/{topic_path}")
    if response.status_code == 200:
        return True, response.json()
    else:
        return False, response.text
