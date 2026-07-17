import streamlit as st
from core.session_state import ensure_defaults
from core.chat_history import append_message, get_history


def render():
    ensure_defaults()
    st.subheader("查询（自然语言）")
    cols = st.columns([3, 1])
    with cols[0]:
        st.text_area("请输入查询，例如：过去 6 个月每月订单数量", key="user_query", height=80)
    with cols[1]:
        if st.button("发送查询"):
            query = st.session_state.get('user_query', '').strip()
            if query:
                append_message('user', query)
                st.session_state['last_query'] = query
                st.success("查询已发送到会话历史，可在右侧查看")
            else:
                st.warning("请输入查询内容")

    st.markdown("---")
    st.subheader("会话历史")
    history = get_history()
    if history:
        for msg in history:
            role = msg.get('role')
            content = msg.get('content')
            if role == 'user':
                st.markdown(f"**用户**: {content}")
            else:
                st.markdown(f"**系统**: {content}")
    else:
        st.info("暂无会话记录")
