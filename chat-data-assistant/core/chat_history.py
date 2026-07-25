# 简单的 chat history 封装（存于 session_state）
import streamlit as st


MAX_MESSAGES = 8


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
    # 返回最近的若干条消息
    return msgs[-max_messages:]


def trim_history(max_messages: int = MAX_MESSAGES):
    """裁剪会话历史，保留最近 `max_messages` 条，并在前面插入一条系统占位摘要，提示上下文已被压缩。"""
    msgs = st.session_state.get('messages', [])
    if not msgs:
        return
    if len(msgs) <= max_messages:
        return
    trimmed = msgs[-max_messages:]
    summary_msg = {"role": "system", "content": "[历史已压缩，仅保留最近对话以节省 token]"}
    st.session_state['messages'] = [summary_msg] + trimmed
