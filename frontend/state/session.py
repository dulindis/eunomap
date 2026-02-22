import streamlit as st
from typing import List, Dict, Any

def init_session():
    """Initializes all necessary session state variables."""
    if "reset_form" not in st.session_state:
        st.session_state.reset_form = False

    if "selected_tags" not in st.session_state:
        st.session_state.selected_tags = []

    if "content_input" not in st.session_state:
        st.session_state.content_input = ""

    if "uploader_key" not in st.session_state:
        st.session_state.uploader_key = 0
        
    if "show_disambiguate" not in st.session_state:
        st.session_state.show_disambiguate = False

def get_content_input() -> str:
    return st.session_state.get("content_input", "")

def set_content_input(value: str):
    st.session_state.content_input = value

def get_selected_tags() -> List[str]:
    return st.session_state.get("selected_tags", [])

def set_selected_tags(tags: List[str]):
    st.session_state.selected_tags = tags

def get_uploader_key() -> int:
    return st.session_state.get("uploader_key", 0)

def trigger_form_reset():
    st.session_state.reset_form = True

def handle_form_reset():
    """Checks if a reset is pending and clears form state if so."""
    if st.session_state.get("reset_form", False):
        clear_form()
        st.session_state.reset_form = False

def clear_form():
    st.session_state.content_input = ""
    st.session_state.selected_tags = []
    st.session_state.uploader_key = get_uploader_key() + 1
    st.session_state.show_disambiguate = False
    
    # Clear any selection state (sel_ keys)
    for key in list(st.session_state.keys()):
        if key.startswith("sel_"):
            del st.session_state[key]

def get_show_disambiguate() -> bool:
    return st.session_state.get("show_disambiguate", False)

def set_show_disambiguate(value: bool):
    st.session_state.show_disambiguate = value

def get_disambiguation_data() -> Dict[str, Any]:
    return st.session_state.get("disambiguation_data", {})

def set_disambiguation_data(data: Dict[str, Any]):
    st.session_state.disambiguation_data = data

def get_last_tags_for_save() -> tuple:
    return st.session_state.get("last_tags_for_save", ())

def set_last_tags_for_save(tags_tuple: tuple):
    st.session_state.last_tags_for_save = tags_tuple

def get_tag_selection(tag: str) -> str:
    return st.session_state.get(f"sel_{tag}", "")

def set_tag_selection(tag: str, value: str):
    st.session_state[f"sel_{tag}"] = value
