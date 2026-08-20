import streamlit as st
from ui.sidebar import render as render_sidebar

def render_settings():
    st.markdown("# Settings")
    st.caption("Manage API, model, database and schema configuration.")
    for item in ["API Configuration","Model Configuration","Database Connection","Schema Management"]:
        st.markdown(f"<div class=\"cd-card\"><h3 style=\"color:white;\">{item}</h3></div>", unsafe_allow_html=True)
    st.markdown("---")
    render_sidebar()
