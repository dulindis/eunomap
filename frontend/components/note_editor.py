import streamlit as st
from components.tag_selector import render_tag_selector, render_disambiguation_ui
from components.media_uploader import render_media_uploader
from services import note_service, tag_service
from state import session

def _resolve_and_check_tags():
    """Resolves tags and returns data of ambiguous tags."""
    selected_tags = session.get_selected_tags()
    disambiguation_needed = {}
    
    for tag in selected_tags:
        result = tag_service.resolve_tag(tag, note_tags=[])
        if result and result.get("status") == "multiple_matches":
            candidates = result.get("candidates", [])
            if candidates:
                disambiguation_needed[tag] = candidates
                
    return disambiguation_needed

def _perform_final_save(content: str, image_file):
    """Saves note and attaches correct tag paths, then resets form."""
    disambiguation_needed = session.get_disambiguation_data()
    selected_tags = session.get_selected_tags()
    
    # First create note without tags
    success, note_response = note_service.create_note(content, tags="", file=image_file)
    if not success:
        st.error(f"Failed to save note: {note_response}")
        return
        
    note_id = note_response.get("id")
    
    # Attach tags
    for tag in selected_tags:
        if tag in disambiguation_needed and disambiguation_needed[tag]:
            # Use user's selection
            selected_path = session.get_tag_selection(tag)
            
            if selected_path == "➕ Create new tag under 'others'":
                new_tag = tag_service.create_tag(tag)
                if new_tag:
                    tag_service.attach_tag(note_id, new_tag.get("id"))
            else:
                # Find the tag ID for the selected path
                all_tags = tag_service.search_tags(tag)
                for t in all_tags:
                    if t.get("path") == selected_path:
                        tag_service.attach_tag(note_id, t.get("id"))
                        break
        else:
            # Did not need disambiguation
            resolve_result = tag_service.resolve_tag(tag, note_tags=[])
            if resolve_result:
                if resolve_result.get("status") == "unique_match":
                    tag_info = resolve_result.get("tag", {})
                    tag_service.attach_tag(note_id, tag_info.get("id"))
                elif resolve_result.get("status") == "not_found":
                    new_tag = tag_service.create_tag(tag)
                    if new_tag:
                        tag_service.attach_tag(note_id, new_tag.get("id"))
                    
    st.success("Note saved!")
    session.trigger_form_reset()
    # Clear selection state
    for key in list(st.session_state.keys()):
        if key.startswith("sel_"):
            del st.session_state[key]
    st.rerun()

def render_note_editor():
    st.header("➕ Add a New Note")
    
    content = st.text_area(
        "Content",
        value=session.get_content_input(),
        key="content_input",
    )
    
    # Reset disambiguation if tags changed
    current_tags = tuple(sorted(session.get_selected_tags()))
    if session.get_last_tags_for_save() != current_tags:
        session.set_last_tags_for_save(current_tags)
        session.set_show_disambiguate(False)
    
    render_tag_selector()
    image_file = render_media_uploader()
    
    if st.button("Save Note"):
        selected_tags = session.get_selected_tags()
        disambiguation_needed = _resolve_and_check_tags()
        has_disambiguation = any(c for c in disambiguation_needed.values() if c)
        
        if has_disambiguation:
            session.set_show_disambiguate(True)
            session.set_disambiguation_data(disambiguation_needed)
        else:
            # Save directly with all tags in the call
            success, response = note_service.create_note(content, tags=",".join(selected_tags), file=image_file)
            if success:
                st.success("Note saved!")
                session.trigger_form_reset()
                st.rerun()
            else:
                st.error(f"Failed to save note: {response}")
                
    # Show disambiguation UI if flagged
    def on_disambiguation_save():
        _perform_final_save(content, image_file)
        
    render_disambiguation_ui(on_disambiguation_save)
