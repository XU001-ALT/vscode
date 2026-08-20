import streamlit as st
from core.translations import t

def render_navigation():
    if "page" not in st.session_state:
        st.session_state.page = "Home"

    pages=[t("home_nav"),t("query_nav"),t("settings_nav")]
    mapping={"Home":pages[0],"AI Query":pages[1],"Settings":pages[2]}
    selected=st.radio("",pages,index=pages.index(mapping[st.session_state.page]),horizontal=True)
    reverse={v:k for k,v in mapping.items()}
    st.session_state.page=reverse[selected]
    return st.session_state.page
