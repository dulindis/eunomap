from typing import List
import inflect
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer, util
from collections import defaultdict

from models import Tag
from utils.tag_utils import tag_processor

# =============================================================================
# Constants
# =============================================================================

# Inflect engine for pluralization/singularization
# _inflect = inflect.engine()


# =============================================================================
# Hierarchy Management
# =============================================================================


# working
# def suggest_tags_from_text_semantic(
#     text: str,
#     db: Session,
#     selected_tags: List[str] | None = None,
#     threshold: float = 0.6,
# ) -> List[str]:
#     """
#     Suggests tags for a given text using exact match and semantic similarity.

#     Args:
#         text: Input text to extract tags from.
#         db: SQLAlchemy database session.
#         selected_tags: Already selected tags to exclude from suggestions.
#         threshold: Minimum similarity score for semantic suggestions.

#     Returns:
#         List of suggested tag names (max MAX_TAGS). If none found, returns ["others"].
#     """
#     if not text:
#         return ["others"]

#     selected_norm = {normalize(t) for t in (selected_tags or [])}
#     text_norm = normalize(text)

#     # Fetch all tags
#     tags = db.query(Tag).all()
#     suggestions = []

#     # Exact matches
#     exact_matches = []
#     remaining_tags_list = []

#     for tag in tags:
#         tag_norm = normalize(tag.name)
#         if tag_norm in selected_norm:
#             continue

#         pattern = rf"(?:^|_){re.escape(tag_norm)}(?:_|$)"
#         if re.search(pattern, text_norm):
#             exact_matches.append(tag.name)
#         else:
#             remaining_tags_list.append(tag)

#     suggestions.extend(exact_matches[:MAX_TAGS])

#     # # Stop if we already reached max tags
#     if len(suggestions) >= MAX_TAGS:
#         return suggestions[:MAX_TAGS]

#     # Semantic similarity for remaining tags
#     if remaining_tags_list and embed_model:
#         tag_texts = [tag.name for tag in remaining_tags_list]
#         tag_norms = [normalize(tag.name) for tag in remaining_tags_list]

#         # Compute embeddings
#         text_emb = embed_model.encode(text_norm, convert_to_tensor=True)
#         tag_embs = embed_model.encode(tag_texts, convert_to_tensor=True)
#         sims = util.cos_sim(text_emb, tag_embs)[0]

#         # Collect tags above threshold
#         sem_suggestions = [
#             tag_texts[i]
#             for i, sim_score in enumerate(sims)
#             if sim_score >= threshold and tag_norms[i] not in selected_norm
#         ]

#         # Sort by similarity
#         sem_suggestions_sorted = [
#             tag
#             for _, tag in sorted(
#                 zip(sims.tolist(), sem_suggestions), key=lambda x: x[0], reverse=True
#             )
#         ]

#         # Add remaining tags up to MAX_TAGS
#         for tag in sem_suggestions_sorted:
#             if len(suggestions) >= MAX_TAGS:
#                 break
#             suggestions.append(tag)

#     # Fallback to "others"
#     if not suggestions:
#         suggestions.append("others")

#     return suggestions
