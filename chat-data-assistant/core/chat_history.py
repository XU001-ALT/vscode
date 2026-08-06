# 简单的 chat history 封装（存于 session_state）
import streamlit as st


def append_message(role, content, **meta):
    """追加一条消息到会话历史。meta 用于携带不展示但需保留的上下文（如上一轮 SQL）。"""
    if 'messages' not in st.session_state:
        st.session_state['messages'] = []
    msg = {"role": role, "content": content}
    msg.update(meta)
    st.session_state['messages'].append(msg)


def clear_history():
    """清空会话消息。"""
    st.session_state['messages'] = []


def get_history(max_messages: int | None = None):
    """返回会话历史，默认返回全部。可传入 `max_messages` 以只返回最近若干条。"""
    msgs = st.session_state.get('messages', [])
    if max_messages is None:
        return msgs
    if len(msgs) <= max_messages:
        return msgs
    return msgs[-max_messages:]
