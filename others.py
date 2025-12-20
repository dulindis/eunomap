import streamlit as st
import pandas as pd
from datetime import datetime
import json, os
from PIL import Image
from tags import tags_map
from Note import Note
from utilities import ensure_folder, add_note
from ExportBuilder import ExportBuilder

# --- Folders ---
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)


# Step 2: Flatten all tags to create autocomplete options
all_tags = sorted({tag for tags in tags_map.values() for tag in tags})

# selected_tags = st.multiselect(
#     "Select or type tags:",
#     options=all_tags,
#     default=None,
#     help="Select existing tags or type new ones",
# )
# tags = [tag for tag in selected_tags if tag not in all_tags]

# Step 5: Optionally add new tags to a "Custom" category
# if tags:
#     if "Custom" not in tags:
#         tags["Custom"] = []
#     tags["Custom"].extend(tags)

# st.write("Selected tags:", selected_tags)
# st.write("Tags map (updated):", tags_map)


st.title("📘 Personal Notes Manager with Tags")

# menu = st.sidebar.radio("Menu", ["Add Note", "View Notes"])

categories = list(tags_map.keys())


# if menu == "Add Note":
st.header("➕ Add a New Note")
tag = st.selectbox("Category", categories)
sub_tags = tags_map.get(tag, [])
sub_tag_selection = st.selectbox("Sub-Category", sub_tags)
title = st.text_input("Title")
content = st.text_area("Content")

selected_tags = st.multiselect(
    "Select or type tags:",
    options=all_tags + sub_tags,
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

# elif menu == "View Notes":
st.header("🔍 Browse Notes")
category = st.selectbox("Choose category", categories)
keyword = st.text_input("Search keyword or tag")
cat_dir = os.path.join(DATA_DIR, category)
json_path = os.path.join(cat_dir, f"{category}.json")

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
            # Filter
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

# st.write("Here's our first attempt at using data to create a table:")

# # st.write("Language (input):")
# input_language = st.text_input("Language (input)", key="language_input")
# output_language = st.text_input("Language (output)", key="language_output")


# st.write(
#     pd.DataFrame(
#         {"Input language": [input_language], "Output language": [output_language]}
#     )
# )

# # st.text_input("Your name", key="name")

# st.button() or st.selectbox()
