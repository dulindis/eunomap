# Future LLM & Semantic Extension Architecture

## 1. Design Philosophy

The system is deterministic-first.

Semantic (LLM/embedding) logic must:

- Augment ranking
- Assist disambiguation
- Improve retrieval relevance

It must NEVER:
- Override canonical normalization
- Bypass tag identity rules
- Directly create tags
- Modify hierarchy automatically

Deterministic engine remains authoritative.

---

## 2. Extension Layers

The architecture becomes 3-layered:

Layer 1 – Canonical Engine (existing)
Layer 2 – Embedding Similarity Engine
Layer 3 – Optional Generative Layer

---

## 3. Layer 1: Deterministic Tag Engine (Authoritative)

Responsible for:

- Normalization
- Canonical key resolution
- Parent-child validation
- Tag creation governance
- Subtree expansion
- Exact & prefix matching

This layer must always execute first.

---

## 4. Layer 2: Embedding Similarity Engine

Purpose:
Enhance suggestion ranking and retrieval.

### 4.1 Embedding Targets

Embeddings should be generated for:

- Tag.key
- Tag.path
- Note.content
- Note.title
- Combined tag context

Stored as:

- Separate table (recommended)
- Vector column (if using Postgres later)
- Local FAISS index (if staying SQLite)

---

### 4.2 Use Cases

#### A) Semantic Tag Suggestion

When deterministic engine returns:

- multiple_matches
- weak contains matches

Embedding engine can:

- Rank candidates by cosine similarity
- Suggest semantically related tags
- Recommend sibling tags

Flow:

1. Deterministic candidates generated
2. Compute similarity(query_embedding, candidate_embedding)
3. Re-rank deterministically sorted list

Deterministic tier priority must remain.

---

#### B) Query Expansion

If user selects:

brands + pets

Embedding engine may:

- Suggest related tags like "pet_clothing"
- Suggest narrower tags like "dog_accessories"

But suggestions must be explicit (not auto-applied).

---

#### C) Related Notes Suggestion

After retrieving deterministic intersection:

Embedding layer may:

- Rank results by semantic closeness
- Suggest additional notes

---

## 5. Layer 3: Generative Markdown (Optional)

This layer may:

- Generate summary of filtered notes
- Create structured report
- Suggest taxonomy gaps

It must:

- Only read data
- Never modify DB
- Never invent canonical tags

Example:

Input:
Tags: brands + pets

Output:

# Brands in Pets

Nike
- 3 notes
- Trending ↑

Adidas
- 2 notes
- Recently added

---

## 6. Embedding Model Strategy

Recommended initial approach:

- sentence-transformers (small local model)
- 384–768 dimension embeddings
- Stored in DB or local index

Avoid:

- Large hosted LLM dependency
- Uncontrolled prompt-based decisions

Embeddings should be:

- Deterministic per content
- Versioned

---

## 7. Hybrid Ranking Formula

Final ranking formula:

score =
  deterministic_score * 0.7
+ embedding_similarity * 0.3
+ trending_boost

Deterministic score always dominates.

If deterministic score == 0:
Semantic may elevate, but never auto-attach.

---

## 8. Embedding Storage Schema (Future)

Table: TagEmbedding
- tag_id (FK)
- vector
- model_version
- updated_at

Table: NoteEmbedding
- note_id (FK)
- vector
- model_version
- updated_at

---

## 9. Migration Strategy

If embedding model changes:

- Increment model_version
- Recompute embeddings
- Keep previous until fully rebuilt

Never mix embedding versions in same query.

---

## 10. Safety Guarantees

Semantic layer must:

- Be read-only
- Never auto-create tags
- Never auto-merge tags
- Never bypass TagProcessor
- Always log ranking decisions

---

## 11. Activation Modes

System should support:

Mode A: Deterministic Only
Mode B: Deterministic + Semantic Ranking
Mode C: Deterministic + Semantic + Generative

Config-driven switch recommended.

---

## 12. Long-Term Evolution

Future possibility:

- Tag similarity clustering
- Auto-detection of taxonomy gaps
- Suggest alias additions
- Suggest pluralization rule updates

All suggestions must require manual approval.

---

# Guiding Principle

Deterministic identity is permanent.
Semantic intelligence is assistive.

Never invert this relationship.