"""聊天面板：消息渲染、用户输入管道（含 Self-Correction 和多轮上下文）。"""
import streamlit as st
from core.session_state import ensure_defaults
from core.chat_history import append_message, get_history
from ai.text_to_sql import to_sql_with_correction
from db.executor import execute_sql_safe


def _run_pipeline(query: str):
    """执行完整的 Text-to-SQL → 执行 → Self-Correction 流水线。

    所有异常都在此捕获，确保不会白屏崩溃，而是以聊天消息形式展示。
    SQL 不展示给顾客，仅通过 meta 存进历史供 LLM 多轮纠错使用。
    """
    schema_summary = st.session_state.get('orm_schema', '')
    if not schema_summary.strip():
        append_message('system', "⚠️ 请先在左侧侧边栏加载 Schema（粘贴表结构或从数据库拉取）")
        return

    history = get_history()

    try:
        sql, df, error = to_sql_with_correction(
            schema_summary=schema_summary,
            chat_history=history,
            user_query=query,
            execute_fn=execute_sql_safe,
        )
    except Exception as e:
        # LLM 调用层面的异常（401、网络超时等），不是 SQL 执行失败
        st.session_state['last_sql'] = None
        st.session_state['last_df'] = None
        error_detail = str(e)
        # 对常见错误给出中文提示
        if '401' in error_detail or 'Authorization' in error_detail or 'Unauthorized' in error_detail:
            hint = "🔑 API Key 无效或未配置，请检查 .env 中的 LLM_API_KEY。"
        elif 'timeout' in error_detail.lower() or 'timed out' in error_detail.lower():
            hint = "⏱️ LLM 请求超时，请稍后重试。"
        elif 'Connection' in error_detail or 'connect' in error_detail.lower():
            hint = "🌐 无法连接到 LLM 服务，请检查网络和 LLM_BASE_URL。"
        else:
            hint = f"❌ 系统错误: {error_detail}"
        append_message('assistant', hint)
        return

    # 始终保存最后一次 SQL
    st.session_state['last_sql'] = sql

    if error:
        # SQL 执行/校验层面的失败（含 Self-Correction 后仍失败）
        st.session_state['last_df'] = None
        append_message('assistant', (
            f"查询执行失败：{error}\n\n"
            f"您可以尝试换个问法，或确认问题在已加载的表结构范围内。"
        ), sql=sql)
    else:
        st.session_state['last_df'] = df
        row_count = len(df) if df is not None else 0
        append_message('assistant', f"已返回 {row_count} 行数据。", sql=sql)
        # 新结果自动聚焦到「图表」Tab（绘图软件的主输出）
        st.session_state['result_tabs'] = '图表'
        # 自动推荐图表配置（基于用户问题 + 结果集），失败则回退手动模式
        try:
            from ai.chart_recommendation import recommend_chart
            st.session_state['chart_recommendation'] = recommend_chart(df, query, sql)
        except Exception:
            st.session_state['chart_recommendation'] = None


def _submit_query(query: str):
    """提交一条查询：写历史 → 跑流水线 → 重跑页面。"""
    query = query.strip()
    if not query:
        return
    with st.chat_message("user"):
        st.markdown(query)
    append_message('user', query)
    _run_pipeline(query)
    st.rerun()


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
        _submit_query(query)
