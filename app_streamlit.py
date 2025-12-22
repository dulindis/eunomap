import streamlit as st
import requests
from datetime import datetime
from PIL import Image
from io import BytesIO
from utils import (
    load_hierarchy,
    flatten_all_tags,
    get_suggestions,
    build_flat_mapping,
)
import json
from streamlit_tags import st_tags

# --- CONFIG ---
API_URL = "http://127.0.0.1:8000"  # FastAPI base URL


# HIERARCHY_FILE = "hierarchy.json"

# Load hierarchy JSON
hierarchy = load_hierarchy()

# Flatten all tags
flat_tags = sorted(set(flatten_all_tags(hierarchy)))

if "reset_form" not in st.session_state:
    st.session_state.reset_form = False

if st.session_state.reset_form:
    st.session_state.content_input = ""
    st.session_state.selected_tags = []
    st.session_state.uploader_key += 1
    st.session_state.reset_form = False


# --- SESSION STATE INIT ---
if "selected_tags" not in st.session_state:
    st.session_state.selected_tags = []

if "content_input" not in st.session_state:
    st.session_state.content_input = ""

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0


# --- CLEAR FORM FUNCTION ---
def clear_note_form():
    st.session_state.content_input = ""
    st.session_state.selected_tags = []
    st.session_state.uploader_key += 1


# Initialize session state
# if "selected_tags" not in st.session_state:
#     st.session_state.selected_tags = []

st.title("📘 Personal Notes Manager")
st.header("➕ Add a New Note")


# if "content_input" not in st.session_state:
#     st.session_state.content_input = ""

content = st.text_area(
    "Content",
    value=st.session_state.content_input,
    key="content_input",
)

st.session_state.selected_tags = st_tags(
    label="Select tags",
    value=st.session_state.selected_tags,
    suggestions=[t for t in flat_tags if t not in st.session_state.selected_tags],
    # key="tags_input",
    key=f"tags_input_{st.session_state.uploader_key}",
    maxtags=5,
)

st.write("Selected tags:", st.session_state.selected_tags)

image_file = st.file_uploader(
    "Attach an image (optional)",
    type=["png", "jpg", "jpeg"],
    # key="image_input",
    key=f"image_input_{st.session_state.uploader_key}",
)

# if st.button(
#     "Save Note"
#     #  , on_click=clear_note_form
# ):
#     # Use selected tags from session state
#     selected_tags = st.session_state.selected_tags
#     data = {"content": content, "tags": ",".join(selected_tags)}
#     if image_file:
#         files = {"file": (image_file.name, image_file, "multipart/form-data")}
#         r = requests.post(f"{API_URL}/notes/", data=data, files=files)
#     else:
#         # No file, just send form-data
#         r = requests.post(f"{API_URL}/notes/", data=data)

#     if r.status_code == 200:
#         st.success(f"Note saved: {content}")
#         clear_note_form()
#         st.rerun()
#     else:
#         st.error(f"Failed to save note: {r.text}")

if st.button("Save Note"):
    selected_tags = st.session_state.selected_tags
    data = {"content": content, "tags": ",".join(selected_tags)}

    if image_file:
        files = {"file": (image_file.name, image_file, "multipart/form-data")}
        r = requests.post(f"{API_URL}/notes/", data=data, files=files)
    else:
        r = requests.post(f"{API_URL}/notes/", data=data)

    if r.status_code == 200:
        st.success("Note saved")

        # ✅ request reset on NEXT rerun
        st.session_state.reset_form = True
        st.rerun()


st.header("🔍 Browse Notes by Topic")
browse_topic = st.text_input("Search by topic/tag")

if browse_topic:
    r = requests.get(f"{API_URL}/generate/{browse_topic.lower()}")
    if r.status_code == 200:
        result = r.json()
        # st.subheader(result["title"])

        for section, notes in result["sections"].items():
            if notes:
                st.markdown(f"### {section}")
                for n in notes:
                    st.markdown(n.get("content", ""))
                    if n.get("media"):
                        st.image(f"{API_URL}/{n['media']}", use_column_width=True)
                    st.markdown(f"Tags: {', '.join(n.get('tags', []))}")
                    st.divider()

        if result.get("remaining"):
            st.markdown("### Remaining")
            for n in result["remaining"]:
                st.markdown(n.get("content", ""))
                if n.get("media"):
                    st.image(f"{API_URL}/{n['media']}", use_column_width=True)
                st.markdown(f"Tags: {', '.join(n.get('tags', []))}")
                st.divider()
    else:
        st.error("Failed to fetch notes")
