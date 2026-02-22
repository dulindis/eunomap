# Internal Knowledge Wiki – Product Specification

## 1. Purpose

This application is a structured internal wiki built around a normalized hierarchical tag system.

The system ensures:

- Deterministic tag identity
- Hierarchical organization
- Controlled tag creation
- Context-aware resolution
- Future semantic extensibility

The system is NOT a free-form tagging system.
It is a controlled taxonomy-driven knowledge graph.

---

## 2. Core Concepts

### 2.1 Note

A Note represents a unit of knowledge.

A Note may contain:
- title
- markdown content
- media (image/file)
- external link
- tags (hierarchical)

Notes are retrieved and filtered by tags.

---

### 2.2 Tag

A Tag is a hierarchical node.

Each tag has:

- id
- label (normalized canonical form)
- key (normalized canonical form)
- path (slug-based hierarchical path)
- parent_id
- stats

Tags form a tree structure.

---

## 3. Tag Identity Rules

- Tags are uniquely identified by `(key + parent_id)`
- `key` is the normalized canonical form
- `label` is always stored as normalized form
- Slugs are only used for path representation
- Raw user input is NEVER stored as canonical identity

---

## 4. Tag Modes

The system supports:

- PATH mode (hierarchical)
- FLAT mode (no parent hierarchy)

Hierarchy is default.

---

## 5. Tag Creation Governance

- Unknown tags are auto-assigned to `/others` if no parent is specified
- Parent tags are auto-created when creating by path
- Tags are normalized BEFORE lookup
- Duplicate tags at same hierarchy level are prohibited

---

## 6. Suggestion Philosophy

Suggestions must be:

- Deterministic
- Ranked
- Based on canonical key
- Context-aware (note_tags optional)

LLM is NOT primary suggestion engine.

---

## 7. Dynamic Markdown

When multiple tags are selected:

Primary behavior:
- Intersection-based filtering (AND)
- Subtree expansion when using hierarchical tags

Future:
- Optional semantic summarization layer

---

## 8. Non-Goals

- No uncontrolled tag creation
- No ambiguous tag identity
- No storing raw inconsistent labels
- No semantic-only retrieval