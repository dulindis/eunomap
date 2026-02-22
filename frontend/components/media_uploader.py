import streamlit as st
from state import session

def render_media_uploader():
    uploader_key = session.get_uploader_key()
    image_file = st.file_uploader(
        "Attach an image (optional)",
        type=["png", "jpg", "jpeg"],
        key=f"image_input_{uploader_key}",
    )
    return image_file
