import os
import requests
from typing import Any, Dict, Optional

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

class MockResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text
        
    def json(self):
        return {"error": self.text}

def get(endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
    url = f"{API_URL}{endpoint}"
    try:
        response = requests.get(url, params=params)
        return response
    except requests.exceptions.ConnectionError:
        return MockResponse(503, "Cannot connect to the backend server. Please make sure the FastAPI server is running on port 8000.")

def post(endpoint: str, json: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None, files: Optional[Dict[str, Any]] = None) -> Any:
    url = f"{API_URL}{endpoint}"
    try:
        response = requests.post(url, json=json, data=data, files=files)
        return response
    except requests.exceptions.ConnectionError:
        return MockResponse(503, "Cannot connect to the backend server. Please make sure the FastAPI server is running on port 8000.")
