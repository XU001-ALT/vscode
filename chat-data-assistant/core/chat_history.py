# 简单的 chat history 封装（存于 session_state）
import streamlit as st


def append_message(role, content):
    if 'messages' not in st.session_state:
        st.session_state['messages'] = []
    st.session_state['messages'].append({"role": role, "content": content})


def get_history():
    return st.session_state.get('messages', [])
