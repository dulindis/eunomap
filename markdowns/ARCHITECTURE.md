# Architecture Specification

## 1. System Overview

Frontend: Streamlit
Backend: FastAPI + SQLAlchemy
Database: SQLite (WAL mode enabled)
Normalization: Central TagProcessor
Hierarchy bootstrapped from JSON

---

## 2. Tag Model Rules

### Identity

Canonical identity = `Tag.key + parent_id`

Constraints:

- key is normalized
- label = normalized key
- path is slug-based
- parent_id nullable for root

Path example:

/health
/health/doctor
/health/doctor/cardiologist

---

## 3. Normalization Pipeline

All tag inputs MUST pass through:

TagProcessor.get_canonical_form()

Pipeline:

1. Unicode normalize
2. Lowercase
3. Alias mapping
4. Remove invalid characters
5. Collapse whitespace
6. Singularize last token (unless in DO_NOT_SINGULARIZE)
7. Generate slug separately

DB storage:
- key = normalized
- label = normalized
- slug derived only for path

---

## 4. Tag Creation Algorithm

### get_or_create_tag

1. Normalize input
2. Resolve parent
3. Lookup by (key + parent_id)
4. If exists → return
5. Else → create
6. Auto-create /others root if needed

---

## 5. Hierarchy Integrity Rules

- Parent must exist before child
- Path always derived from parent.path + slug
- Path never manually edited
- Renaming requires subtree rebuild

---

## 6. Trending Ranking

Trending score formula:

last_24h_count / (total_count + 1)

Ranking must be deterministic.

No random ordering.

---

## 7. Subtree Retrieval

To fetch notes by tag subtree:

- Slugify path
- Prefix match using LIKE
- Use DISTINCT to avoid duplication

Subtree includes:
- exact tag
- all descendants

---

## 8. Dynamic Markdown Engine

Primary logic:

- Multiple selected tags → AND intersection
- Each tag expands to subtree
- Results must match all selected subtrees

Algorithm:

1. Expand each tag to subtree prefix
2. Query notes matching each subtree
3. Intersect note sets

Future extension:
Optional semantic re-ranking layer.

---

## 9. Performance Guarantees

- SQLite WAL enabled
- Foreign keys enforced
- Distinct queries for subtree
- Normalized lookup before insert

Expected scale:
- < 10k notes
- < 5k tags

---

## 10. LLM Extension Boundary

LLM may:

- Suggest alternative tags
- Rank ambiguous matches
- Generate summary markdown

LLM may NOT:

- Override canonical normalization
- Create tags automatically
- Modify hierarchy structure