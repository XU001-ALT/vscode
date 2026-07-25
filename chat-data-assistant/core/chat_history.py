# 简单的 chat history 封装（存于 session_state）
import streamlit as st


def append_message(role, content):
    if 'messages' not in st.session_state:
        st.session_state['messages'] = []
    st.session_state['messages'].append({"role": role, "content": content})


def get_history(max_messages: int | None = None):
    """返回会话历史，默认返回全部。可传入 `max_messages` 以只返回最近若干条。"""
    msgs = st.session_state.get('messages', [])
    if max_messages is None:
        return msgs
    if len(msgs) <= max_messages:
        return msgs
    return msgs[-max_messages:]
