# =============================================================================
# Tag Normalization Constants - FINAL COMPLETE VERSION
# =============================================================================
# This module contains normalization rules for tag processing.
# Updated: January 7, 2026
# Includes: Base normalization + Painting domain additions

DO_NOT_SINGULARIZE = {
    # =========================================================================
    # Abstract/Uncountable Nouns
    # =========================================================================
    "analytics",
    "data",
    "design",
    "development",
    "earnings",  # financial term
    "equipment",
    "finance",
    "fitness",
    "goods",  # economics term
    "hardware",
    "media",
    "mindfulness",
    "money",
    "music",
    "news",
    "research",
    "series",
    "software",
    "wellness",
    # =========================================================================
    # Medical Conditions & Diseases (non-pluralizable)
    # =========================================================================
    "adhd",
    "aids",
    "alzheimers",
    "arthritis",
    "diabetes",
    "hiv",
    "measles",
    "mumps",
    "osteoporosis",
    "parkinsons",
    # =========================================================================
    # Body Parts (Always Plural Form)
    # =========================================================================
    "arms",  # body part (both meanings: limbs & weapons)
    "gums",
    "hormones",
    "intestines",
    "kidneys",
    "lungs",
    # =========================================================================
    # Technology Terms
    # =========================================================================
    "ai",
    "ml",
    "nodejs",
    # =========================================================================
    # People & Age Groups
    # =========================================================================
    "children",
    "kids",
    # =========================================================================
    # Always-Plural or Irregular Nouns
    # =========================================================================
    "clothes",
    "glasses",  # always plural
    "headquarters",
    "outdoors",
    "pants",  # always plural
    "scissors",  # always plural
    "species",
    # =========================================================================
    # Category/Taxonomy Nouns (Collections)
    # =========================================================================
    "accessories",
    "basics",
    "cosmetics",
    "electronics",
    "groceries",
    "podcasts",
    "quotes",
    "services",
    "shoes",
    "toiletries",
    # =========================================================================
    # Art Materials (Always Plural Collections)
    # =========================================================================
    "brushes",
    "materials",
    "paints",
    "pigments",
    "supplies",
    # =========================================================================
    # Art Categories
    # =========================================================================
    "arts",
    "crafts",
    "graphics",
    # =========================================================================
    # Compound Terms
    # =========================================================================
    "interview_tips",
    "streaming_services",
    "tips_and_tricks",
    "workplace_skills",
    # =========================================================================
    # Helper/Guide Terms
    # =========================================================================
    "tips",
    "tricks",
    # =========================================================================
    # Academic Disciplines ("-ics" suffix)
    # =========================================================================
    "aesthetics",
    "economics",
    "ethics",
    "linguistics",
    "mathematics",
    "physics",
    "politics",
    "statistics",
}


ALIASES = {
    # =========================================================================
    # AI & Machine Learning
    # =========================================================================
    "ai & ml": "ai_ml",
    "ai and ml": "ai_ml",
    "ai/ml": "ai_ml",
    "artificial intelligence": "ai",
    "machine learning": "ml",
    "machine_learning": "ml",
    "ml/ai": "ai_ml",
    # =========================================================================
    # Programming Languages & Frameworks
    # =========================================================================
    ".net": "dotnet",
    "c#": "csharp",
    "c sharp": "csharp",
    "c++": "cpp",
    "java script": "javascript",
    "js": "javascript",
    "node js": "nodejs",
    "node.js": "nodejs",
    "react js": "react",
    "react.js": "react",
    "vue.js": "vue",
    # =========================================================================
    # Health & Medical Conditions
    # =========================================================================
    "alzheimer's": "alzheimers",
    "alzheimer's disease": "alzheimers",
    "covid": "covid-19",
    "covid19": "covid-19",
    "health & wellness": "health_and_wellness",
    "hiv aids": "hiv_aids",
    "hiv/aids": "hiv_aids",
    "mental health": "mental_health",
    "parkinson disease": "parkinsons",
    "parkinson's": "parkinsons",
    "parkinson's disease": "parkinsons",
    "well being": "wellness",
    "well-being": "wellness",
    "wellbeing": "wellness",
    # =========================================================================
    # Body Parts & Anatomy
    # =========================================================================
    "belly": "abdomen",
    "tummy": "abdomen",
    # =========================================================================
    # Food & Nutrition
    # =========================================================================
    "food & drink": "food_and_drink",
    "fruit & vegetables": "fruit_and_vegetables",
    "meat & seafood": "meat_and_seafood",
    # =========================================================================
    # Media & Entertainment
    # =========================================================================
    "film": "movie",
    "television": "tv",
    "tv series": "tv",
    "tv show": "tv",
    # =========================================================================
    # Painting Techniques
    # =========================================================================
    "alla prima": "alla_prima",
    "fat over lean": "fat_over_lean",
    "plein air": "plein_air",
    "thick over thin": "thick_over_thin",
    "wet on wet": "wet_on_wet",
    "wet-on-wet": "wet_on_wet",
    # =========================================================================
    # Art Materials & Brands
    # =========================================================================
    "michael harding": "michael_harding",
    "old holland": "old_holland",
    "rosemary & co": "rosemary_and_co",
    "rosemary and co": "rosemary_and_co",
    "winsor & newton": "winsor_newton",
    "winsor and newton": "winsor_newton",
    # =========================================================================
    # Paint Colors
    # =========================================================================
    "alizarin crimson": "alizarin_crimson",
    "burnt sienna": "burnt_sienna",
    "burnt umber": "burnt_umber",
    "cadmium red": "cadmium_red",
    "cadmium yellow": "cadmium_yellow",
    "ivory black": "ivory_black",
    "raw sienna": "raw_sienna",
    "raw umber": "raw_umber",
    "titanium white": "titanium_white",
    "ultramarine blue": "ultramarine_blue",
    "yellow ochre": "yellow_ochre",
    # =========================================================================
    # Painting Surfaces
    # =========================================================================
    "acrylic primed": "acrylic_primed",
    "belgian linen": "belgian_linen",
    "oil primed": "oil_primed",
    # =========================================================================
    # Art Terminology
    # =========================================================================
    "color theory": "color_theory",
    "light and shadow": "light_and_shadow",
    "still life": "still_life",
    "value study": "value_study",
    # =========================================================================
    # Languages (Non-English → English)
    # =========================================================================
    "ciekawostki": "trivia",
    "ciekawostki jezykowe": "language_trivia",
    "deutsch": "german",
    "español": "spanish",
    "français": "french",
    "italiano": "italian",
    "português": "portuguese",
    "中文": "chinese",
    # =========================================================================
    # Business & General Terms
    # =========================================================================
    "co-op": "coop",
    "e-commerce": "ecommerce",
    "q&a": "q_and_a",
    "r&d": "r_and_d",
    "start-up": "start_up",
    "startup": "start_up",
    "tips & tricks": "tips_and_tricks",
    "tips and tricks": "tips_and_tricks",
    "wi-fi": "wi_fi",
    "wifi": "wi_fi",
    # =========================================================================
    # Taxonomy Preferences (Canonical Forms)
    # =========================================================================
    "breweries": "brewery",
    "children": "kids",
    "exercise": "workout",
    "firm": "company",
    "hardware": "equipment",
    "perfume": "fragrance",
    "pet care": "pet_care",
    "scent": "fragrance",
    "taxes": "tax",
    "paint": "color",
}
