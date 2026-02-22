# Frontend Refactor Plan

## Goal
Modularize the Streamlit app into a clean, maintainable architecture with:
- Page separation
- Reusable UI components
- Centralized API client layer
- No database access from frontend
- Centralized session state management

---

## 1. Target Folder Structure

```
frontend/
├── main.py              # Minimal entry point
├── pages/
│   ├── 1_Create_Note.py
│   ├── 2_Search_Notes.py
│   └── 3_Trending.py
├── components/
│   ├── tag_selector.py
│   ├── note_editor.py
│   ├── note_list.py
│   └── media_uploader.py
├── services/
│   ├── api_client.py
│   ├── tag_service.py
│   └── note_service.py
├── state/
│   └── session.py
└── utils/
    └── formatters.py
```

---

## 2. Rules

### 2.1 Frontend Must NEVER:
- Import SQLAlchemy
- Access database directly
- Implement tag resolution logic
- Implement ranking logic
- Recreate backend normalization logic
- Use raw `st.session_state` scattered everywhere

### 2.2 main.py Must Be Minimal
```python
import streamlit as st

st.set_page_config(page_title="Eunomap")
st.title("Eunomap")
st.write("Select a page from sidebar")
```

---

## 3. Services Layer

### 3.1 API Client (`services/api_client.py`)
- Central HTTP wrapper for all backend calls
- Handles authentication
- Error handling

### 3.2 Tag Service (`services/tag_service.py`)
```python
def resolve_tag(label: str, note_tags: list[str]) -> TagResolutionResult
def create_tag(label: str, parent_path: str) -> Tag
def get_or_create_tag(label: str, parent_path: str) -> Tag
def get_notes_by_subtree(path: str) -> list[Note]
```

### 3.3 Note Service (`services/note_service.py`)
```python
def create_note(content: str, tags: list[str]) -> Note
def search_notes(query: str) -> list[Note]
def upload_media(file) -> str
```

---

## 4. State Management

All session state operations through `state/session.py`:
```python
def set_selected_tags(tags: list[str])
def get_selected_tags() -> list[str]
def clear_form()
# etc.
```

No raw `st.session_state` outside this file.

---

## 5. Refactor Order

1. Create folder structure
2. Extract API client wrapper
3. Create services layer
4. Build state/session.py
5. Create reusable components
6. Split into pages
7. Clean main.py last

---

## 6. Validation Checklist

- [ ] No DB imports in frontend
- [ ] No business logic in pages
- [ ] main.py < 20 lines
- [ ] All API calls via services/api_client.py
- [ ] Session state isolated
- [ ] No duplicated tag normalization logic
