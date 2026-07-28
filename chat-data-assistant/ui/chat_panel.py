"""聊天面板：消息渲染、用户输入管道（含 Self-Correction 和多轮上下文）。"""
import streamlit as st
from core.session_state import ensure_defaults
from core.chat_history import append_message, get_history
from ai.text_to_sql import to_sql_with_correction
from db.executor import execute_sql_safe


def _run_pipeline(query: str):
    """执行完整的 Text-to-SQL → 执行 → Self-Correction 流水线。"""
    schema_summary = st.session_state.get('orm_schema', '')
    if not schema_summary.strip():
        append_message('system', "⚠️ 请先在左侧侧边栏加载 Schema（粘贴表结构或从数据库拉取）")
        return

    history = get_history()

    sql, df, error = to_sql_with_correction(
        schema_summary=schema_summary,
        chat_history=history,
        user_query=query,
        execute_fn=execute_sql_safe,
    )

    # 始终保存最后一次 SQL
    st.session_state['last_sql'] = sql

    if error:
        # 执行失败：保存 SQL 到上下文便于追问调试
        st.session_state['last_df'] = None
        append_message('assistant', (
            f"SQL 执行失败: {error}\n\n"
            f"生成的最新 SQL:\n```sql\n{sql}\n```\n\n"
            f"您可以尝试追问或修改查询条件。"
        ))
    else:
        st.session_state['last_df'] = df
        row_count = len(df) if df is not None else 0
        # 将成功执行的 SQL 和数据摘要注入上下文，便于多轮追问
        sql_preview = sql[:300] + "..." if len(sql) > 300 else sql
        append_message('assistant', (
            f"已返回 {row_count} 行数据\n\n"
            f"```sql\n{sql_preview}\n```"
        ))


def render():
    """渲染聊天面板。"""
    ensure_defaults()

    # 渲染历史消息
    history = get_history()
    for msg in history:
        role = msg.get('role', 'system')
        content = msg.get('content', '')
        if role == 'user':
            with st.chat_message("user"):
                st.markdown(content)
        elif role == 'system':
            with st.chat_message("assistant"):
                st.info(content)
        else:
            with st.chat_message("assistant"):
                st.markdown(content)

    # 输入框
    query = st.chat_input("请输入查询，例如：查看所有实验数据中温度大于500的记录")
    if query:
        query = query.strip()
        if query:
            with st.chat_message("user"):
                st.markdown(query)
            append_message('user', query)
            _run_pipeline(query)
            st.rerun()
