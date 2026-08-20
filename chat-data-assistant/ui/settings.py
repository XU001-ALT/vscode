import streamlit as st
from ui.sidebar import render as render_sidebar

def render_settings():
    st.markdown("# Settings")
    st.caption("Manage existing configuration.")
    render_sidebar()
