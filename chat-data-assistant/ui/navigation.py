import streamlit as st

def render_navigation():
    if "page" not in st.session_state:
        st.session_state.page="Home"
    st.sidebar.markdown("# chat-data")
    pages=["Home","AI Query","Settings"]
    st.session_state.page=st.sidebar.radio("",pages,index=pages.index(st.session_state.page))
    return st.session_state.page
