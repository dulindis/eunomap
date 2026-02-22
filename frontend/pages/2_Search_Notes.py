import streamlit as st
from components.note_list import render_search_and_list
from state import session

st.set_page_config(page_title="Search Notes - Eunomap")

session.init_session()

render_search_and_list()
