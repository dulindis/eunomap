import re
import unicodedata

from sqlalchemy.orm import Session

from models import Tag, TagStats
from tag_normalization_config import DO_NOT_SINGULARIZE, ALIASES


# =============================================================================
# Tag Normalization
# =============================================================================


class TagProcessor:
    """Centralized tag processing with shared logic."""

    def __init__(self, aliases: dict = None, do_not_singularize: set = None):
        self.aliases = aliases or ALIASES
        self.do_not_singularize = do_not_singularize or DO_NOT_SINGULARIZE

    def _preprocess(self, text: str) -> str:
        """Common preprocessing for both normalize and slugify."""
        if not text:
            return ""

        # Unicode normalization
        text = unicodedata.normalize("NFKC", text)
        text = text.strip().lower()

        # Apply aliases (canonical forms)
        text = self.aliases.get(text, text)

        return text

    def normalize(self, text: str) -> str:
        """
        Normalize a string into a stable tag key.
        Used for: tag lookups, comparisons, deduplication
        """
        text = self._preprocess(text)

        # Keep special chars that are meaningful for tags
        # text = re.sub(r"[^a-z0-9\s_\-#\+&]", "", text)
        text = re.sub(r"[^a-z0-9\s_\-#\+&]", "", text)

        # Collapse whitespace
        text = re.sub(r"\s+", " ", text)

        # Spaces → underscores (tag convention)
        text = text.replace(" ", "_")

        # Normalize separators
        text = re.sub(r"_+", "_", text)
        text = text.strip("_")

        return text

    def slugify(self, text: str) -> str:
        """
        Convert a string into a URL/path-safe slug.
        Used for: filesystem paths, URLs
        """
        text = self._preprocess(text)

        # Convert to ASCII only (paths need to be universally safe)
        text = unicodedata.normalize("NFKD", text)
        text = text.encode("ascii", "ignore").decode("ascii")

        # Replace spaces & underscores with hyphens (URL convention)
        text = re.sub(r"[\s_]+", "-", text)

        # Remove anything not alphanumeric or hyphen
        text = re.sub(r"[^a-z0-9\-]+", "", text)

        # Collapse multiple hyphens
        text = re.sub(r"-+", "-", text)
        text = text.strip("-")

        return text

    def get_canonical_form(self, text: str) -> tuple[str, str]:
        """
        Get both normalized and slugified forms at once.
        Returns: (normalized_key, slug_for_path)
        """
        preprocessed = self._preprocess(text)

        # Branch from preprocessed text
        normalized = self.normalize_from_preprocessed(preprocessed)
        slugified = self.slugify_from_preprocessed(preprocessed)

        return normalized, slugified

    def normalize_from_preprocessed(self, text: str) -> str:
        """Skip preprocessing if already done."""
        # Keep special chars that are meaningful for tags
        text = re.sub(r"[^a-z0-9\s_\-#\+&]", "", text)
        text = re.sub(r"\s+", " ", text)
        text = text.replace(" ", "_")
        text = re.sub(r"_+", "_", text)
        text = text.strip("_")
        return text

    def slugify_from_preprocessed(self, text: str) -> str:
        """Skip preprocessing if already done."""
        text = unicodedata.normalize("NFKD", text)
        text = text.encode("ascii", "ignore").decode("ascii")
        text = re.sub(r"[\s_]+", "-", text)
        text = re.sub(r"[^a-z0-9\-]+", "", text)
        text = re.sub(r"-+", "-", text)
        text = text.strip("-")
        return text


# Create a singleton instance
tag_processor = TagProcessor(ALIASES, DO_NOT_SINGULARIZE)


# Export the instance if direct access needed
def get_processor() -> TagProcessor:
    return tag_processor


# # region Convenience functions for backward compatibility


# def normalize(text: str) -> str:
#     """Normalize a string into a stable tag key."""
#     return tag_processor.normalize(text)


# def slugify(text: str) -> str:
#     """Convert a string into a URL/path-safe slug."""
#     return tag_processor.slugify(text)


# def process_tag(text: str) -> dict:
#     """
#     Process a tag text into all needed forms.

#     Returns dict with:
#     - original: The input text
#     - normalized: For lookups/comparisons
#     - slug: For paths/URLs
#     """
#     normalized, slug = tag_processor.get_canonical_form(text)
#     return {"original": text, "normalized": normalized, "slug": slug}


# # Simple usage (backward compatible)
# # key = normalize("AI/ML")          # "ai_ml"
# # path_component = slugify("AI/ML") # "ai-ml"
# #
# # # Class-based usage (more control)
# # processor = TagProcessor(custom_aliases, custom_do_not_singularize)
# # key = processor.normalize("Machine Learning")
# #
# # # Efficient batch processing
# # tag = "Machine Learning"
# # result = process_tag(tag)
# # result = {
# #     "original": "Machine Learning",
# #     "normal

# =============================================================================
# Tag Database Operations
# =============================================================================


# Tag retrieval and creation:
def get_or_create_tag(
    db: Session,
    label: str,
    parent: Tag | None = None,
    auto_others: bool = True,
) -> Tag:
    """
    Get or create a hierarchical tag node.

    - label (DB): normalized key (not original input)
    - key: same normalized key
    - path: composed of slug segments
    """
    if label is None or not label.strip():
        raise ValueError("Tag label cannot be empty")

    # Normalize & slugify once
    normalized_key, slug = tag_processor.get_canonical_form(label)

    # Ensure pending parent has an id
    if parent is not None and parent.id is None:
        db.flush()

    # Auto-assign to root "others" if no parent
    if not parent and auto_others and normalized_key != "others":
        others_label = "others"
        others_key, others_slug = tag_processor.get_canonical_form(others_label)

        others_tag = (
            db.query(Tag)
            .filter(
                Tag.key == others_key,
                Tag.parent_id.is_(None),
            )
            .first()
        )

        if not others_tag:
            others_tag = Tag(
                label=others_key,  # store normalized in label
                key=others_key,
                parent=None,
                path=f"/{others_slug}",
            )
            db.add(others_tag)
            db.flush()

        parent = others_tag

    # Look up by normalized key + parent
    query = db.query(Tag).filter(Tag.key == normalized_key)

    if parent:
        query = query.filter(Tag.parent_id == parent.id)
    else:
        query = query.filter(Tag.parent_id.is_(None))

    tag = query.first()
    if tag:
        return tag

    # Build path from slug
    path = f"{parent.path}/{slug}" if parent else f"/{slug}"

    # Store normalized in both label and key
    tag = Tag(
        label=normalized_key,
        key=normalized_key,
        parent=parent,
        path=path,
    )

    db.add(tag)
    db.flush()

    return tag


# Add tags to the database
def add_tags(
    hierarchy,
    parent_tag: Tag | None = None,
    db: Session | None = None,
) -> None:
    """
    Recursively add tags from a hierarchy structure.

    Supports:
    - dict: { "Health": {...} }
    - list: ["Dogs", "Cats"]
    - str:  "Health"
    """

    if hierarchy is None:
        return

    # Dict → node with children
    if isinstance(hierarchy, dict):
        for label, children in hierarchy.items():
            tag = get_or_create_tag(db, label, parent=parent_tag, auto_others=False)
            add_tags(children, parent_tag=tag, db=db)

    # List → multiple siblings
    elif isinstance(hierarchy, list):
        for item in hierarchy:
            add_tags(item, parent_tag=parent_tag, db=db, auto_others=False)

    # String → leaf node
    elif isinstance(hierarchy, str):
        get_or_create_tag(db, hierarchy, parent=parent_tag, auto_others=False)

    else:
        raise TypeError(f"Unsupported hierarchy type: {type(hierarchy)}")


# =============================================================================
# Autocomplete Suggestions
# =============================================================================
# Maximum number of tags to suggest (for semantic search)
MAX_TAGS = 4

# Load a small embedding model once
# embed_model = SentenceTransformer("all-MiniLM-L6-v2")  # fast, small


def find_exact_tag_matches(
    text_norm: str,
    tags: list[Tag],
    selected_norm: set[str],
) -> tuple[list[str], list[Tag]]:
    """
    Finds exact tag matches in text.

    Returns:
        - list of matched tag names
        - list of remaining Tag objects (not matched)
    """
    matches: list[str] = []

    for tag in tags:
        tag_norm = tag_processor.normalize(tag.name)

        if tag_norm in selected_norm:
            continue

        if tag_norm in text_norm:
            matches.append(tag.name)

    return matches


def suggest_tags_from_text_semantic(
    text: str,
    db: Session,
    selected_tags: list[str] | None = None,
    threshold: float = 0.6,
) -> list[str]:
    if not text:
        return ["others"]

    text_norm = tag_processor.normalize(text)
    selected_norm = {tag_processor.normalize(t) for t in (selected_tags or [])}

    tags = db.query(Tag).all()
    suggestions: list[str] = []

    # 1️⃣ Exact matches
    exact_matches = find_exact_tag_matches(
        text_norm=text_norm,
        tags=tags,
        selected_norm=selected_norm,
    )
    exact_matches_sorted = sorted(
        exact_matches,
        key=lambda t: text_norm.count(tag_processor.normalize(t)),
        reverse=True,
    )
    suggestions.extend(exact_matches_sorted[:MAX_TAGS])

    if len(suggestions) >= MAX_TAGS:
        return suggestions[:MAX_TAGS]

    matched_norms = {tag_processor.normalize(t) for t in exact_matches}
    remaining_tags = [
        tag
        for tag in tags
        if tag_processor.normalize(tag.name) not in matched_norms
        and tag_processor.normalize(tag.name) not in selected_norm
    ]

    # 2️⃣ Semantic matches
    if remaining_tags and embed_model:
        tag_texts = [tag.name for tag in remaining_tags]
        tag_norms = [tag_processor.normalize(tag.name) for tag in remaining_tags]

        text_emb = embed_model.encode(text_norm, convert_to_tensor=True)
        tag_embs = embed_model.encode(tag_texts, convert_to_tensor=True)
        sims = util.cos_sim(text_emb, tag_embs)[0]

        sem_candidates = [
            (sims[i].item(), tag_texts[i])
            for i in range(len(tag_texts))
            if sims[i] >= threshold and tag_norms[i] not in selected_norm
        ]

        sem_candidates.sort(key=lambda x: x[0], reverse=True)
        # TODO: make sure that the synonym doesnt exist in extact matches
        for _, tag in sem_candidates:
            if len(suggestions) >= MAX_TAGS:
                break
            suggestions.append(tag)

    return suggestions or ["others"]


def get_suggestions(selected_tags, current_input, flat_mapping) -> list[str]:
    if selected_tags:
        last_tag = selected_tags[-1].lower()
        suggestions = flat_mapping.get(last_tag, list(flat_mapping.keys()))
    else:
        suggestions = list(flat_mapping.keys())

    return [
        s
        for s in suggestions
        if s.lower().startswith(
            current_input.lower()
        )  # This will never work for transcriptions.
        and s.lower() not in [t.lower() for t in selected_tags]
    ]


def suggest_tags_from_text(
    text: str,
    db: Session,
    selected_tags: list[str] | None = None,
) -> list[str]:

    if not text:
        return ["others"]
    # Normalize selected tags
    selected_norm = {tag_processor.normalize(t) for t in (selected_tags or [])}

    text_norm = tag_processor.normalize(text)
    tags = db.query(Tag).all()
    # for t in db.query(Tag).all():
    #     print("TAGI TESTOWE:", t.name)

    matches = find_exact_tag_matches(
        text_norm=text_norm,
        tags=tags,
        selected_norm=selected_norm,
    )

    if not matches:
        return ["others"]

    return sorted(
        matches,
        key=lambda t: text_norm.count(tag_processor.normalize(t)),
        reverse=True,
    )


def get_trending_tags(db, limit: int = 20):
    q = (
        db.query(Tag, TagStats)
        .join(TagStats, TagStats.tag_id == Tag.id)
        .order_by((TagStats.last_24h_count / (TagStats.total_count + 1.0)).desc())
        .limit(limit)
    )
    return [
        TagOut(
            id=tag.id,
            label=tag.label,
            path=tag.path,
            stats=TagStatsOut(
                total_count=stats.total_count,
                last_24h_count=stats.last_24h_count,
                last_7d_count=stats.last_7d_count,
                trending_score=(
                    stats.last_24h_count / (stats.total_count + 1.0)
                    if stats.total_count is not None
                    else None
                ),
                last_used_at=stats.last_used_at,
            ),
        )
        for tag, stats in q.all()
    ]
