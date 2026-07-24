import streamlit as st
from core.session_state import ensure_defaults
from core.chat_history import append_message, get_history
from ai.text_to_sql import to_sql
from db.executor import execute_sql_safe


def _run_pipeline(query: str):
    schema_summary = st.session_state.get('orm_schema', '')
    if not schema_summary.strip():
        append_message('system', "请先在左侧侧边栏加载 Schema（粘贴表结构或从数据库拉取）")
        return

    history = get_history()

    try:
        sql = to_sql(schema_summary, history, query)
    except Exception as e:
        append_message('system', f"SQL 生成失败: {e}")
        return

    st.session_state['last_sql'] = sql

    df, err = execute_sql_safe(sql)
    if err:
        append_message('system', f"SQL 执行失败: {err}")
    else:
        st.session_state['last_df'] = df
        append_message('system', f"已生成 SQL 并返回 {len(df)} 行数据")


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
                _run_pipeline(query)
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
