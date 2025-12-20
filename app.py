import streamlit as st
import pandas as pd
from datetime import datetime
import json, os
from PIL import Image
from tags import tags_map
from Note import Note
from utilities import ensure_folder, add_note, flatten
from ExportBuilder import ExportBuilder

# --- Folders ---
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# --- Flatten all tags (supports nested dicts/lists)
all_tags = sorted(set(flatten(tags_map)))

st.title("📘 Personal Notes Manager with Tags")

categories = list(tags_map.keys())


# ==================================================
#                ADD NOTE SECTION
# ==================================================
st.header("➕ Add a New Note")

# Pick category
category = st.selectbox("Category", categories)

# Handle nested tags (dict = nested categories, list = leaf)
sub_data = tags_map.get(category, [])
if isinstance(sub_data, dict):
    sub_tags = list(sub_data.keys())
elif isinstance(sub_data, list):
    sub_tags = sub_data
else:
    sub_tags = []

sub_category = st.selectbox("Sub-Category", sub_tags)

# Get final sub-tags if nested deeper
final_tag_options = []
selected_branch = sub_data.get(sub_category) if isinstance(sub_data, dict) else None

if isinstance(selected_branch, list):
    final_tag_options = selected_branch

title = st.text_input("Title")
content = st.text_area("Content")

# Allow combining general, subcategory, and all_tags
selected_tags = st.multiselect(
    "Select or type tags:",
    options=all_tags + sub_tags + final_tag_options,
    default=None,
    help="Select existing tags or type new ones",
)

image_file = st.file_uploader("Attach an image (optional)", type=["png", "jpg", "jpeg"])

if st.button("Save Note"):
    image_path = None

    if image_file:
        img_folder = os.path.join(DATA_DIR, category, "images")
        ensure_folder(img_folder)
        img_name = f"{datetime.now().isoformat().replace(':','-')}_{image_file.name}"
        image_path = os.path.join(img_folder, img_name)
        with open(image_path, "wb") as f:
            f.write(image_file.getbuffer())

    note = Note(
        title=title,
        content=content,
        category=category,
        tags=selected_tags,
        image_path=image_path,
    )
    add_note(note)
    st.success(f"Note saved under {category} with tags: {', '.join(selected_tags)}")


# ==================================================
#                VIEW NOTES SECTION
# ==================================================
st.header("🔍 Browse Notes")

browse_category = st.selectbox("Choose category to browse", categories)
keyword = st.text_input("Search keyword or tag")

cat_dir = os.path.join(DATA_DIR, browse_category)
json_path = os.path.join(cat_dir, f"{browse_category}.json")

notes = []
if os.path.exists(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        for n in data:
            note_obj = Note(
                title=n["title"],
                content=n["content"],
                category=n["category"],
                tags=n.get("tags", []),
                image_path=n.get("image"),
                timestamp=n.get("timestamp"),
            )

            if (
                not keyword
                or keyword.lower() in n["content"].lower()
                or keyword.lower() in " ".join(n.get("tags", [])).lower()
            ):
                notes.append(note_obj)

    export = ExportBuilder(notes)

    for note in notes:
        st.markdown(note.to_markdown())
        if note.image_path and os.path.exists(note.image_path):
            st.image(Image.open(note.image_path), use_container_width=True)
        st.divider()

    if notes:
        st.download_button(
            "Export as Markdown",
            export.to_markdown().encode("utf-8"),
            "notes_export.md",
        )
        st.download_button(
            "Export as JSON",
            json.dumps(export.to_json(), indent=2, ensure_ascii=False).encode("utf-8"),
            "notes_export.json",
        )
