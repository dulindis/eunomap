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
    Returns a dict mapping tag name to list of candidates ONLY for multiple_matches.
    """
    disambiguation_needed = {}

    for tag in tags:
        payload = {"label": tag, "note_tags": existing_tags or []}
        r = requests.post(f"{API_URL}/tags/resolve", json=payload)

        if r.status_code == 200:
            result = r.json()
            if result.get("status") == "multiple_matches":
                # Only add to disambiguation if there are actual candidates
                candidates = result.get("candidates", [])
                if candidates:
                    disambiguation_needed[tag] = candidates
            # Note: We don't handle not_found here - those tags will be created automatically

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


# Initialize session state for showing disambiguation UI
if "show_disambiguate" not in st.session_state:
    st.session_state.show_disambiguate = False

# Reset when tags change
current_tags = tuple(sorted(st.session_state.selected_tags))
if "last_tags_for_save" not in st.session_state:
    st.session_state.last_tags_for_save = current_tags
elif st.session_state.last_tags_for_save != current_tags:
    st.session_state.last_tags_for_save = current_tags
    st.session_state.show_disambiguate = False

# Handle save - single unified flow
if st.button("Save Note"):
    # Resolve all tags
    disambiguation_needed = resolve_tags_with_disambiguation(
        st.session_state.selected_tags
    )
    
    # Check if any need disambiguation
    has_disambiguation = any(
        candidates for candidates in disambiguation_needed.values() if candidates
    )
    
    if has_disambiguation:
        # Show disambiguation UI
        st.session_state.show_disambiguate = True
        st.session_state.disambiguation_data = disambiguation_needed
    else:
        # No disambiguation needed - save directly
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
            st.session_state.show_disambiguate = False
            st.rerun()
        else:
            st.error(f"Failed to save note: {r.text}")

# Show disambiguation UI if flagged
if st.session_state.get("show_disambiguate"):
    disambiguation_needed = st.session_state.get("disambiguation_data", {})
    
    if disambiguation_needed:
        st.warning("⚠️ Some tags need your attention:")
        
        # Only show radio buttons for tags that have candidates
        for tag in st.session_state.selected_tags:
            if tag in disambiguation_needed and disambiguation_needed[tag]:
                candidates = disambiguation_needed[tag]
                
                # Show selection for this tag
                st.markdown(f"**{tag}**")
                
                # Show available paths to choose from (only exact label matches, not children)
                for c in candidates:
                    st.markdown(f"  - {c.get('label')} → `{c.get('path')}`")
                
                # Let user select
                options = [f"{c.get('path')}" for c in candidates]
                options.append("➕ Create new tag under 'others'")
                
                selected_path = st.radio(
                    f"Choose path for '{tag}':", options, key=f"radio_{tag}"
                )
                
                # Store selection
                if f"sel_{tag}" not in st.session_state:
                    st.session_state[f"sel_{tag}"] = selected_path

        st.markdown("---")

        # Save with selected paths
        if st.button("Confirm Save"):
            # Create note without tags first
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
                
                # Attach each tag properly
                for tag in st.session_state.selected_tags:
                    if tag in disambiguation_needed and disambiguation_needed[tag]:
                        # Tag needed disambiguation - use user's selection
                        selected_path = st.session_state.get(f"sel_{tag}", "")

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
                            # Find and attach existing tag by path
                            search_r = requests.get(f"{API_URL}/tags/search?q={tag}")
                            if search_r.status_code == 200:
                                all_tags = search_r.json()
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
                        # Tag didn't need disambiguation - resolve and attach it
                        # This handles unique_match and not_found tags
                        resolve_payload = {"label": tag}
                        resolve_r = requests.post(f"{API_URL}/tags/resolve", json=resolve_payload)
                        if resolve_r.status_code == 200:
                            resolve_result = resolve_r.json()
                            if resolve_result.get("status") == "unique_match":
                                # Use the matched tag
                                tag_info = resolve_result.get("tag", {})
                                attach_payload = {
                                    "note_id": note_id,
                                    "tag_id": tag_info.get("id"),
                                }
                                requests.post(f"{API_URL}/tags/attach", json=attach_payload)
                            elif resolve_result.get("status") == "not_found":
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

                st.success("Note saved!")
                st.session_state.reset_form = True
                st.session_state.show_disambiguate = False
                # Clear selection state
                for key in list(st.session_state.keys()):
                    if key.startswith("sel_"):
                        del st.session_state[key]
                st.rerun()


def resolve_topic_with_disambiguation(topic: str, context_topics: list[str] = None) -> dict:
    """
    Resolve a topic and return result.
    Uses existing /tags/resolve endpoint with normalization.
    """
    payload = {"label": topic, "note_tags": context_topics or []}
    r = requests.post(f"{API_URL}/tags/resolve", json=payload)
    
    if r.status_code == 200:
        return r.json()
    return None


def generate_markdown_from_notes(result: dict) -> str:
    """
    Generate markdown with proper heading hierarchy.
    Root tag = H1, deeper entries = H2, H3, etc.
    """
    md_lines = []
    
    # Get the root from title
    title = result.get("title", "")
    if title:
        md_lines.append(f"# {title}\n")
    
    # Process sections (subsections)
    for section, notes in result.get("sections", {}).items():
        if notes:
            md_lines.append(f"## {section}\n")
            for n in notes:
                content = n.get("content", "")
                if content:
                    md_lines.append(f"- {content}")
                if n.get("media"):
                    md_lines.append(f"  - 📎 [Media]({n.get('media')})")
                tags = n.get("tags", [])
                if tags:
                    md_lines.append(f"  - Tags: {', '.join(tags)}")
            md_lines.append("")
    
    # Remaining notes
    if result.get("remaining"):
        md_lines.append("## Other Notes\n")
        for n in result.get("remaining", []):
            content = n.get("content", "")
            if content:
                md_lines.append(f"- {content}")
            tags = n.get("tags", [])
            if tags:
                md_lines.append(f"  - Tags: {', '.join(tags)}")
        md_lines.append("")
    
    return "\n".join(md_lines)


st.header("🔍 Browse Notes by Topic")
browse_topic = st.text_input("Search by topic/tag (comma-separated for multiple)", key="browse_topic")

if browse_topic:
    # Handle multiple topics (comma-separated)
    topics = [t.strip() for t in browse_topic.split(",") if t.strip()]
    
    if len(topics) > 1:
        # Multiple topics - use each resolved tag as context for others
        # First pass: resolve all with context from already-resolved
        resolved_topics = {}
        
        for topic in topics:
            # Use previously resolved topics as context
            context = [resolved_topics[k]["label"] for k in resolved_topics]
            resolved = resolve_topic_with_disambiguation(topic, context_topics=context)
            resolved_topics[topic] = resolved
            
            if resolved and resolved.get("status") == "unique_match":
                context.append(resolved.get("tag", {}).get("label", ""))
        
        # Check if any need disambiguation
        disambiguate_needed = {k: v for k, v in resolved_topics.items() 
                               if v and v.get("status") == "multiple_matches"}
        
        if disambiguate_needed:
            st.warning("⚠️ Multiple matches found for some topics:")
            
            user_selections = {}
            for topic, resolved in disambiguate_needed.items():
                candidates = resolved.get("candidates", [])
                st.markdown(f"**{topic}:**")
                options = [c.get("path") for c in candidates]
                selected = st.radio(f"Choose path for '{topic}':", options, key=f"browse_{topic}")
                user_selections[topic] = selected
            
            # Now fetch notes for selected paths
            for topic, selected_path in user_selections.items():
                if selected_path:
                    topic_path = selected_path.strip("/")
                    r = requests.get(f"{API_URL}/generate/{topic_path}")
                    if r.status_code == 200:
                        result = r.json()
                        md_content = generate_markdown_from_notes(result)
                        st.markdown("---")
                        st.markdown(f"### 📄 {selected_path}")
                        st.code(md_content, language="markdown")
        else:
            # All resolved - fetch notes for each
            for topic in topics:
                resolved = resolved_topics.get(topic)
                if resolved and resolved.get("status") == "unique_match":
                    tag_path = resolved.get("tag", {}).get("path", "")
                    topic_path = tag_path.strip("/")
                    r = requests.get(f"{API_URL}/generate/{topic_path}")
                    if r.status_code == 200:
                        result = r.json()
                        md_content = generate_markdown_from_notes(result)
                        st.markdown("---")
                        st.markdown(f"### 📄 {tag_path}")
                        st.code(md_content, language="markdown")
    elif len(topics) == 1:
        # Single topic - use the existing logic
        topic = topics[0]
        
        # First resolve the topic with normalization and disambiguation
        resolved = resolve_topic_with_disambiguation(topic)
        
        if resolved:
            if resolved.get("status") == "multiple_matches":
                # Need disambiguation
                candidates = resolved.get("candidates", [])
                st.warning(f"⚠️ Multiple '{topic}' tags found. Which one interests you?")
                
                for i, c in enumerate(candidates):
                    st.markdown(f"  - {c.get('label')} → `{c.get('path')}`")
                
                # Let user select
                options = [c.get("path") for c in candidates]
                selected_path = st.radio("Select one:", options, key="browse_topic_select")
                
                if selected_path:
                    topic_path = selected_path.strip("/")
                    r = requests.get(f"{API_URL}/generate/{topic_path}")
                    
                    if r.status_code == 200:
                        result = r.json()
                        md_content = generate_markdown_from_notes(result)
                        st.markdown("---")
                        st.markdown("### 📄 Generated Markdown")
                        st.code(md_content, language="markdown")
            
            elif resolved.get("status") == "unique_match":
                tag_path = resolved.get("tag", {}).get("path", "")
                topic_path = tag_path.strip("/")
                r = requests.get(f"{API_URL}/generate/{topic_path}")
                
                if r.status_code == 200:
                    result = r.json()
                    md_content = generate_markdown_from_notes(result)
                    st.markdown("---")
                    st.markdown("### 📄 Generated Markdown")
                    st.code(md_content, language="markdown")
            
            elif resolved.get("status") == "not_found":
                st.info(f"❌ Tag '{topic}' not found in hierarchy")
                suggested = resolved.get("suggested_parents", [])
                if suggested:
                    st.write("Did you mean:")
                    for s in suggested:
                        st.markdown(f"  - `{s.get('path')}`")
        else:
            # Fallback
            r = requests.get(f"{API_URL}/generate/{topic.lower()}")
            if r.status_code == 200:
                result = r.json()
                md_content = generate_markdown_from_notes(result)
                st.code(md_content, language="markdown")
    else:
        st.info("Enter at least one topic to browse")
