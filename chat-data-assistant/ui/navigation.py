import streamlit as st
from core.translations import t

def render_navigation():
    if "page" not in st.session_state:
        st.session_state.page = "Home"

    pages=[t("home_nav"),t("query_nav"),t("settings_nav")]
    mapping={"Home":pages[0],"AI Query":pages[1],"Settings":pages[2]}
    reverse={v:k for k,v in mapping.items()}

    def _on_nav_change():
        raw = st.session_state.get("_nav_radio")
        if raw in reverse:
            st.session_state.page = reverse[raw]

    current_label = mapping.get(st.session_state.page, pages[0])
    st.radio(
        "", pages,
        index=pages.index(current_label),
        key="_nav_radio",
        horizontal=True,
        on_change=_on_nav_change,
    )
    return st.session_state.page
