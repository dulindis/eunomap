# Backend Refactor Specification

## Goal
**Modularize FastAPI Backend into Domain-Based Architecture**

### 1. Objective

Refactor the current monolithic `main.py` FastAPI file into a clean, modular architecture with:

- Clear separation of concerns  
- Domain-based routers  
- Dedicated service layer  
- Infrastructure isolated from business logic  
- Zero duplication of tag or note logic  
- Minimal logic inside route handlers  

**After refactor:**

- `main.py` must be under 30 lines  
- All business logic must live in `services/`  
- All HTTP wiring must live in `api/`  
- No database queries inside route handlers  

---

### 2. Target Folder Structure

Create the following structure inside the backend:

backend/
│
├── main.py
│
├── core/
│ ├── config.py
│ ├── lifespan.py
│ ├── security.py
│
├── api/
│ ├── router.py
│ ├── deps.py
│ ├── notes.py
│ ├── tags.py
│ ├── auth.py
│ ├── llm.py
│ ├── export.py
│
├── services/
│ ├── note_service.py
│ ├── tag_service.py
│ ├── audio_service.py
│ ├── llm_service.py
│
├── models/
├── schemas/
├── utils/
├── db/


If folders already exist, reorganize accordingly.

---

### 3. Refactor Rules (STRICT)

#### 3.1 main.py Rules

After refactor, `main.py` must:

- Initialize FastAPI  
- Mount static files  
- Attach lifespan  
- Include the root API router  
- Nothing else  

**Final structure should resemble:**

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from core.lifespan import lifespan
from api.router import api_router

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(api_router)

No business logic allowed.

4. Router Layer Separation
4.1 Create api/router.py
This file must register all domain routers.

Example:

from fastapi import APIRouter
from . import notes, tags, auth, llm, export

api_router = APIRouter()

api_router.include_router(notes.router, prefix="/notes", tags=["notes"])
api_router.include_router(tags.router, prefix="/tags", tags=["tags"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(llm.router, prefix="/llm", tags=["llm"])
api_router.include_router(export.router, prefix="/export", tags=["export"])


5. Domain Router Responsibilities
Each file inside api/ must:

Each file inside api/ must:

Define router = APIRouter()

Contain only HTTP wiring

Call service-layer functions

Contain zero database query logic

Contain zero ranking logic

Contain zero normalization logic

Routes must delegate.

5.1 api/notes.py
Move into this file:

create_note

create_note_protected

upload_image

upload_audio

import_markdown_note

Subtree note fetching

→ Routes must call note_service.

5.2 api/tags.py
Move into this file:

resolve_tag

create_tag

attach_tag

search_tags

get_subtree

Tag mode endpoints

Hierarchy endpoints

→ Routes must call tag_service.

5.3 api/auth.py
Move into this file:

User creation

Token login

GitHub OAuth endpoints

→ Security logic may use core/security.py.

5.4 api/llm.py
Move into this file:

export_for_llm

apply_llm_suggestions

→ Must call llm_service.

5.5 api/export.py
Move into this file:

Subtree markdown export

Note export utilities

6. Service Layer Responsibilities
The services/ directory contains ALL business logic.

Services may:

Query database

Perform ranking

Handle tag resolution

Handle hierarchy inference

Perform normalization

Coordinate between models

Services may NOT:

Import FastAPI

Return HTTP responses

Raise HTTPException directly

They should raise domain exceptions instead.

6.1 tag_service.py
Must contain:

get_or_create_tag

get_or_create_tag_by_path

resolve_tag logic

Context-based disambiguation

Best parent selection

Subtree query logic

Tag mode handling

→ All tag logic must live here.

6.2 note_service.py
Must contain:

Note creation

Note update

Tag attachment during creation

Subtree note retrieval

Markdown import parsing

Timestamp handling

6.3 audio_service.py
Move Whisper model loading here.

Requirements:

Lazy load Whisper model

Singleton pattern

No model loading in main.py

Example:
_model = None

def get_model():
    global _model
    if _model is None:
        # load model here
        pass
    return _model


6.4 llm_service.py
Must contain:

Export logic formatting

Suggestion application logic

Hierarchy reorganization logic

7. Lifespan Extraction
Move all startup/shutdown logic to:

core/lifespan.py

This includes:

Database initialization

Table creation

Startup logging

main.py must import lifespan from here.

8. Dependency Isolation
Create:

api/deps.py

Move:

get_db

get_current_user

Security dependencies

All routes must import dependencies from here.

9. Refactor Safety Order
Perform refactor in this exact order:

Create folder structure

Create api/router.py

Extract routers one by one

Move logic into services gradually

Replace direct DB usage in routes

Move lifespan handling

Shrink main.py last

Do not attempt full rewrite in one step.

10. Post-Refactor Validation Checklist
After refactor, confirm:

main.py < 30 lines

No SQLAlchemy queries inside api/*

No Whisper loading outside services/audio_service.py

No tag resolution logic inside api/tags.py

All domain logic centralized in services/

App runs successfully

No circular imports

11. Architectural Constraints Going Forward
From now on:

All new business logic goes into services/

Routes only orchestrate request/response

No cross-domain imports between routers

Shared utilities must live in utils/

No duplication of normalization logic

12. Long-Term Maintainability Goal
This structure ensures:

Deterministic tag engine stability

LLM boundary isolation

Safe hierarchy evolution

Clean testability

Agent-friendly codebase

Refactor resilience