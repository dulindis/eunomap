import streamlit as st
from state import session
# from state import session

st.set_page_config(page_title="Eunomap", page_icon="📘")

# Initialize session state globally
session.init_session()

st.title("📘 Eunomap")
st.write("Welcome to your Personal Notes Manager!")
st.write("👈 Select an option from the sidebar to get started.")
