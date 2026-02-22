import streamlit as st
from components.note_editor import render_note_editor
from state import session

st.set_page_config(page_title="Create Note - Eunomap")

session.init_session()
session.handle_form_reset()

render_note_editor()
