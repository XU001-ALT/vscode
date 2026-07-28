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

    history = get_history()
    for msg in history:
        role = msg.get('role', 'system')
        content = msg.get('content', '')
        if role == 'user':
            with st.chat_message("user"):
                st.markdown(content)
        else:
            with st.chat_message("assistant"):
                st.markdown(content)

    st.markdown('<p class="section-header">选择图表类型</p>', unsafe_allow_html=True)
    chart_options = {"折线图": "line", "柱状图": "bar", "散点图": "scatter", "饼图": "pie"}
    chart_label = st.radio(
        "图表类型",
        list(chart_options.keys()),
        horizontal=True,
        key="chart_type_selector"
    )
    st.session_state['chart_type'] = chart_options[chart_label]

    query = st.chat_input("请输入查询，例如：某个表的最大数据")
    if query:
        query = query.strip()
        if query:
            with st.chat_message("user"):
                st.markdown(query)
            append_message('user', query)
            _run_pipeline(query)
            st.rerun()
