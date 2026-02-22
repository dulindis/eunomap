# Eunomap - Personal Knowledge Base

A FastAPI-based personal wiki and note-taking system with hierarchical tagging, markdown support, and AI-ready architecture.

## Table of Contents
- [Quick Start](#quick-start)
- [Project Overview](#project-overview)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Database Setup](#database-setup)
- [Running the Application](#running-the-application)
- [Environment Variables](#environment-variables)
- [Tag System](#tag-system)
  - [Tag Modes](#tag-modes)
  - [Context-Aware Resolution](#context-aware-resolution)
- [API Endpoints](#api-endpoints)
- [Markdown Import/Export](#markdown-importexport)
- [LLM Integration](#llm-integration)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

```bash
# 1. Navigate to project
cd c:\dev\python\eunomap

# 2. Install dependencies
pip install poetry
poetry install

# 3. Reset and seed database with hierarchy
poetry run python reset_db.py
# (Database auto-seeds on startup if RESET_DB=true)

# 4. Run the server
poetry run uvicorn main:app --reload

# 5. Open browser
# Frontend: http://localhost:8000
# API docs: http://localhost:8000/docs
```

---

## Project Overview

Eunomap is a personal knowledge management system with:

- **Hierarchical Tags**: Organize notes in tree structures (e.g., `Health/Doctors/Cardiologist`)
- **Dual Tag Modes**: Path-based (Mode A) or flat with LLM inference (Mode B)
- **Context-Aware Resolution**: Automatically resolves ambiguous tags based on existing note tags
- **Markdown Support**: Import/export notes with YAML front matter
- **LLM-Ready**: Export data for AI analysis and apply hierarchy suggestions

---

## Prerequisites

- Python 3.13+
- SQLite (included) or PostgreSQL (optional)
- Poetry (for dependency management)

---

## Installation

### Using Poetry (Recommended)

```bash
# Install Poetry if you don't have it
pip install poetry

# Navigate to project
cd c:\dev\python\eunomap

# Install all dependencies
poetry install

# Install with optional whisper (audio transcription)
poetry install --extras whisper
```

### Using pip

```bash
pip install -r requirements.txt
```

> Note: Check `pyproject.toml` for exact dependencies.

---

## Database Setup

### Option 1: Reset Database (Fresh Start)

```bash
# Method A: Run the reset script
poetry run python reset_db.py

# Method B: Set environment variable (auto-resets on startup)
# Add to .env:
RESET_DB=true

# Then start the app - it will auto-reseed
poetry run uvicorn main:app --reload
```

### Option 2: Manual Seeding

```python
from db import load_initial_data, get_db_session
from utils.hierarchy_utils import load_hierarchy
from utils.tag_utils import add_tags

# Load and seed hierarchy
with get_db_session() as db:
    hierarchy = load_hierarchy("hierarchy.json")
    add_tags(hierarchy, db=db)
    db.commit()
```

### Understanding the Hierarchy

The `hierarchy.json` file defines your tag structure:

```json
{
  "Health": {
    "Doctor": ["Cardiologist", "Neurologist"],
    "Nutrition": ["Dieting", "Superfood"]
  },
  "Travel": {
    "Places": {
      "Europe": ["Poland", "Germany"],
      "Asia": ["Japan", "China"]
    }
  }
}
```

This creates tags like:
- `/health`
- `/health/doctor`
- `/health/doctor/cardiologist`
- `/travel`
- `/travel/places/europe/poland`

---

## Running the Application

### Development Server

```bash
# Basic startup (auto-seeds if tables empty)
poetry run uvicorn main:app --reload

# With custom port
poetry run uvicorn main:app --reload --port 8080

# Production
poetry run uvicorn main:app --host 0.0.0.0 --port 8000
```

### Access Points

| URL | Description |
|-----|-------------|
| `http://localhost:8000` | Main application |
| `http://localhost:8000/docs` | Swagger API documentation |
| `http://localhost:8000/redoc` | ReDoc alternative docs |

---

## Environment Variables

Create a `.env` file in the project root:

```bash
# ===========================================
# REQUIRED (for production)
# ===========================================

DATABASE_URL=sqlite:///./eunomap.db
# Or for PostgreSQL:
# DATABASE_URL=postgresql://user:password@localhost/eunomap

# ===========================================
# OPTIONAL - Application Settings
# ===========================================

# Reset database on startup (true/false)
# WARNING: Deletes all data!
RESET_DB=false

# ===========================================
# OPTIONAL - Tag System Configuration
# ===========================================

# Tag mode: "path" (hierarchical) or "flat" (LLM-managed)
TAG_MODE=path

# Enable/disable disambiguation UI
# When true: shows selection dialog for ambiguous tags
# When false: auto-creates or uses first match
TAG_DISAMBIGUATION_ENABLED=true

# Auto-create tags that don't exist
TAG_AUTO_CREATE=true

# Default parent for new tags (in flat mode)
# TAG_DEFAULT_PARENT=others

# ===========================================
# OPTIONAL - Authentication (GitHub OAuth)
# ===========================================

GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret

# ===========================================
# OPTIONAL - JWT Settings
# ===========================================

JWT_SECRET_KEY=your_secret_key_here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

---

## Tag System

### Tag Modes

#### Mode A: Path-Based (Default)

Tags are hierarchical paths:
```
/health
/health/doctors
/health/doctors/cardiologist
/kids/doctors
/work/doctors
```

When you add "doctors" to a note, the system searches for existing `/health/doctors`, `/kids/doctors`, `/work/doctors` and asks you to choose.

#### Mode B: Flat (LLM-Managed)

Tags are simple names:
```
doctors
pediatrics
cardiology
```

Hierarchy is inferred later by an LLM. Set `TAG_MODE=flat` to enable.

### Context-Aware Resolution

When adding a tag to a note that already has tags, the system uses context:

**Example:**
- Note has tag: `endocrinologist` (path: `/health/doctors/endocrinologist`)
- You add: `doctors`
- System automatically selects: `/health/doctors` (because endocrinologist is under health)

This works because the system finds common parent paths.

### Frontend Integration

```javascript
// When user adds a tag, call resolve first
const result = await fetch('/tags/resolve', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    label: 'doctors',
    existing_tags: ['endocrinologist']  // or note_id
  })
});
const data = await result.json();

if (data.status === 'unique_match') {
  // Auto-attach - show data.tag.path to user
  attachTag(data.tag.id);
} else if (data.status === 'multiple_matches') {
  // Show selection dialog
  showSelectionDialog(data.candidates);
} else if (data.status === 'not_found') {
  // Offer to create new
  showCreateDialog(data.suggested_parents);
}
```

---

## API Endpoints

### Tag Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tags/resolve` | Resolve tag with optional context |
| POST | `/tags/create` | Create new tag |
| POST | `/tags/attach` | Attach tag to note |
| GET | `/tags/mode` | Get current tag mode |
| POST | `/tags/mode` | Set tag mode |
| GET | `/tags/search?q=query` | Search tags |
| GET | `/tags/hierarchy` | Get full hierarchy tree |
| GET | `/tags/subtree/{path}` | Get tags in subtree |

### Notes

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/notes/` | Create note with tags |
| POST | `/upload/` | Upload image with tags |
| POST | `/upload_audio/` | Transcribe audio & suggest tags |

### Import/Export

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/import/markdown` | Import markdown file |
| GET | `/export/subtree/{path}` | Export subtree as ZIP |
| GET | `/export/llm` | Export for LLM analysis |
| POST | `/import/llm/suggestions` | Apply LLM suggestions |

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/token` | Get JWT token |
| POST | `/users/` | Register user |
| GET | `/auth/github/callback` | GitHub OAuth |

---

## Markdown Import/Export

### Export Format

```markdown
---
id: 1
title: Finding a Doctor
created_at: 2024-01-15T10:30:00
updated_at: 2024-01-15T10:30:00
tag_mode: "path"
tags:
  - "health/doctors"
  - "kids/doctors"
---

# Finding a Doctor

Content here...
```

### Import

```bash
curl -X POST http://localhost:8000/import/markdown \
  -F "file=@note.md"
```

---

## LLM Integration

### Export for LLM

```bash
curl http://localhost:8000/export/llm
```

Returns JSON with all notes and tags for hierarchy analysis.

### Apply Suggestions

```bash
curl -X POST http://localhost:8000/import/llm/suggestions \
  -H "Content-Type: application/json" \
  -d '{
    "tag_mappings": [
      {"old_tag_id": 1, "new_path": "health/medical/doctors", "action": "rename"}
    ],
    "new_root_categories": ["emergency"],
    "reasoning": "Consolidated doctor categories"
  }'
```

Use `dry_run=true` to preview changes without applying.

---

## Testing

```bash
# Run all tests
poetry run pytest

# Run specific test file
poetry run pytest tests/test_tag_modes.py

# Run with coverage
poetry run pytest --cov=. --cov-report=html

# Run specific test
poetry run pytest tests/test_tag_modes.py::test_resolve_multiple_matches_path_mode -v
```

---

## Troubleshooting

### Database Locked Error

```bash
# SQLite sometimes locks. Close all connections and retry.
# Or increase timeout in db.py:
cursor.execute("PRAGMA busy_timeout=30000")
```

### Module Not Found

```bash
# Ensure you're in the correct directory
cd c:\dev\python\eunomap

# Or use absolute imports
```

### Port Already in Use

```bash
# Find and kill the process
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Or use different port
poetry run uvicorn main:app --port 8080
```

### Reset Everything

```bash
# Delete the database file
rm eunomap.db

# Or set RESET_DB=true and restart
```

---

## Project Structure

```
eunomap/
├── main.py              # FastAPI app and endpoints
├── config.py            # Configuration settings
├── db.py                # Database setup and session management
├── models.py            # SQLAlchemy models
├── schemas.py           # Pydantic schemas
├── auth.py              # Authentication utilities
├── hierarchy.json       # Initial tag hierarchy
├── utils/
│   ├── tag_modes.py    # Tag strategy pattern
│   ├── tag_utils.py    # Tag operations
│   ├── markdown_utils.py # Markdown import/export
│   ├── llm_utils.py    # LLM integration hooks
│   ├── hierarchy_utils.py
│   └── ...
├── tests/
│   ├── test_tag_modes.py
│   └── ...
└── static/              # Uploaded files
```

---

## Common Tasks

### Add a New Tag Category

Edit `hierarchy.json`:
```json
{
  "New Category": {
    "Subcategory": ["Item1", "Item2"]
  }
}
```

Then reset the database:
```bash
poetry run python reset_db.py
```

### Switch to Flat Tags Mode

Add to `.env`:
```bash
TAG_MODE=flat
TAG_DISAMBIGUATION_ENABLED=false
```

Restart the server.

### Export All Notes

```bash
# Export entire database as markdown
curl http://localhost:8000/export/subtree/ -o export.zip
```

---

## License

MIT License
