import streamlit as st
from streamlit_tags import st_tags
from services import tag_service
from state import session
from utils.formatters import flatten_hierarchy

@st.cache_data(ttl=300, show_spinner=False)
def get_flat_tags():
    hierarchy = tag_service.get_hierarchy()
    tags = flatten_hierarchy(hierarchy)
    if not tags:
        # If it's empty (e.g. backend down), clear the cache so it retries next time
        st.cache_data.clear()
    return tags

def render_tag_selector():
    flat_tags = get_flat_tags()
    selected_tags = session.get_selected_tags()
    uploader_key = session.get_uploader_key()
    
    selected = st_tags(
        label="Select tags",
        value=selected_tags,
        suggestions=[t for t in flat_tags if t not in selected_tags],
        key=f"tags_input_{uploader_key}",
        maxtags=5,
    )
    
    session.set_selected_tags(selected)
    st.write("Selected tags:", selected)
    return selected

def render_disambiguation_ui(on_save_callback):
    """Renders the disambiguation section and saves when resolved."""
    if not session.get_show_disambiguate():
        return
        
    disambiguation_needed = session.get_disambiguation_data()
    if not disambiguation_needed:
        return
        
    st.warning("⚠️ Some tags need your attention:")
    
    selected_tags = session.get_selected_tags()
    
    # Only show radio buttons for tags that have candidates
    for tag in selected_tags:
        if tag in disambiguation_needed and disambiguation_needed[tag]:
            candidates = disambiguation_needed[tag]
            
            st.markdown(f"**{tag}**")
            
            # Show available paths to choose from
            for c in candidates:
                st.markdown(f"  - {c.get('label')} → `{c.get('path')}`")
            
            # Let user select
            options = [f"{c.get('path')}" for c in candidates]
            options.append("➕ Create new tag under 'others'")
            
            selected_path = st.radio(
                f"Choose path for '{tag}':", options, key=f"radio_{tag}"
            )
            
            # Store selection in session
            session.set_tag_selection(tag, selected_path)
    
    st.markdown("---")
    
    if st.button("Confirm Save"):
        on_save_callback()
