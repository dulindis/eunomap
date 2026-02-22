from io import BytesIO
import json
import requests

import streamlit as st
from datetime import datetime
from PIL import Image
from utils.tag_utils import get_suggestions
from utils.hierarchy_utils import build_flat_mapping, flatten_all_tags, load_hierarchy

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


st.title("📘 Personal Notes Manager")
st.header("➕ Add a New Note")


content = st.text_area(
    "Content",
    value=st.session_state.content_input,
    key="content_input",
)

st.session_state.selected_tags = st_tags(
    label="Select tags",
    value=st.session_state.selected_tags,
    suggestions=[t for t in flat_tags if t not in st.session_state.selected_tags],
    key=f"tags_input_{st.session_state.uploader_key}",
    maxtags=5,
)

st.write("Selected tags:", st.session_state.selected_tags)

image_file = st.file_uploader(
    "Attach an image (optional)",
    type=["png", "jpg", "jpeg"],
    key=f"image_input_{st.session_state.uploader_key}",
)


def resolve_tags_with_disambiguation(
    tags: list[str], existing_tags: list[str] = None
) -> dict:
    """
    Resolve tags and return any that need disambiguation.
    Returns a dict mapping tag name to list of candidates.
    """
    disambiguation_needed = {}

    for tag in tags:
        payload = {"label": tag, "note_tags": existing_tags or []}
        r = requests.post(f"{API_URL}/tags/resolve", json=payload)

        if r.status_code == 200:
            result = r.json()
            if result.get("status") == "multiple_matches":
                disambiguation_needed[tag] = result.get("candidates", [])
            elif result.get("status") == "not_found":
                # Tag doesn't exist - add to disambiguation to show "not found" message
                # Only add suggestions if there are actual related matches
                suggested = result.get("suggested_parents", [])
                disambiguation_needed[tag] = suggested if suggested else []

    return disambiguation_needed


def show_tag_selection_modal(tag_name: str, candidates: list) -> str:
    """Show a modal for the user to select the right tag."""
    options = [f"{c.get('label')} ({c.get('path')})" for c in candidates]
    options.append("Create new tag")

    selected = st.select_box(
        f"Multiple tags found for '{tag_name}'. Select one:",
        options,
        key=f"select_{tag_name}",
    )

    if selected == "Create new tag":
        return None  # Will create new

    # Extract the selected path
    for c in candidates:
        if f"{c.get('label')} ({c.get('path')})" == selected:
            return c.get("path")

    return None


if st.button("Save Note"):
    # First, check if any tags need disambiguation
    disambiguation_needed = resolve_tags_with_disambiguation(
        st.session_state.selected_tags
    )

    # If disambiguation needed, show selection UI
    final_tags = []

    if disambiguation_needed:
        st.warning("⚠️ Some tags need your attention:")
        
        for tag in st.session_state.selected_tags:
            if tag in disambiguation_needed:
                candidates = disambiguation_needed[tag]
                
                # Show selection for this tag
                st.markdown(f"**{tag}**")
                
                if candidates:
                    # Show available paths to choose from
                    for i, c in enumerate(candidates):
                        st.markdown(f"  - {c.get('label')} → `{c.get('path')}`")
                    
                    # Let user select
                    options = [f"{c.get('path')}" for c in candidates]
                    options.append("➕ Create new tag under 'others'")
                    
                    selected_path = st.radio(
                        f"Choose path for '{tag}':", options, key=f"radio_{tag}"
                    )

                    if selected_path == "➕ Create new tag under 'others'":
                        final_tags.append(tag)
                    else:
                        # Use the selected path - extract the label
                        final_tags.append(selected_path.split("/")[-1])
                else:
                    # No similar tags found - tag doesn't exist in tree
                    st.info(f"❌ Tag '{tag}' doesn't exist in the current hierarchy")
                    st.markdown("  Will create new tag under 'others'")
                    final_tags.append(tag)
            else:
                final_tags.append(tag)

        st.markdown("---")

        # Confirm button - attach tags by ID
        if st.button("Confirm and Save Note"):
            # First create the note without tags
            data = {"content": content, "tags": ""}

            if image_file:
                files = {"file": (image_file.name, image_file, "multipart/form-data")}
                r = requests.post(f"{API_URL}/notes/", data=data, files=files)
            else:
                r = requests.post(f"{API_URL}/notes/", data=data)

            if r.status_code != 200:
                st.error(f"Failed to save note: {r.text}")
            else:
                note = r.json()
                note_id = note.get("id")
                
                # Now attach each tag properly
                for tag in st.session_state.selected_tags:
                    if tag in disambiguation_needed:
                        # Get user's selection from radio button
                        selected_path = st.session_state.get(f"radio_{tag}", "")

                        if selected_path == "➕ Create new tag under 'others'":
                            # Create new tag
                            create_payload = {"label": tag}
                            create_r = requests.post(
                                f"{API_URL}/tags/create", json=create_payload
                            )
                            if create_r.status_code == 200:
                                new_tag = create_r.json()
                                attach_payload = {
                                    "note_id": note_id,
                                    "tag_id": new_tag.get("id"),
                                }
                                requests.post(f"{API_URL}/tags/attach", json=attach_payload)
                        else:
                            # Find the tag at the selected path
                            # Search for tags with this label
                            search_r = requests.get(f"{API_URL}/tags/search?q={tag}")
                            if search_r.status_code == 200:
                                all_tags = search_r.json()
                                # Find matching path
                                for t in all_tags:
                                    if t.get("path") == selected_path:
                                        attach_payload = {
                                            "note_id": note_id,
                                            "tag_id": t.get("id"),
                                        }
                                        requests.post(
                                            f"{API_URL}/tags/attach", json=attach_payload
                                        )
                                        break
                    else:
                        # Regular tag - let backend handle it
                        pass  # Already handled by note creation

                st.success("Note saved")
                st.session_state.reset_form = True
                st.rerun()
    else:
        # No disambiguation needed, save directly
        selected_tags = st.session_state.selected_tags
        data = {"content": content, "tags": ",".join(selected_tags)}

        if image_file:
            files = {"file": (image_file.name, image_file, "multipart/form-data")}
            r = requests.post(f"{API_URL}/notes/", data=data, files=files)
        else:
            r = requests.post(f"{API_URL}/notes/", data=data)

        if r.status_code == 200:
            st.success("Note saved")
            st.session_state.reset_form = True
            st.rerun()
        else:
            st.error(f"Failed to save note: {r.text}")


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
