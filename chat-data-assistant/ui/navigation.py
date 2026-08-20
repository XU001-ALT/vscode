
import streamlit as st


def render_navigation():
    if "page" not in st.session_state:
        st.session_state.page = "Home"

    pages = ["Home", "AI Query", "Settings"]

    st.session_state.page = st.radio(
        "Navigation",
        pages,
        index=pages.index(st.session_state.page),
        horizontal=True,
    )

    return st.session_state.page
