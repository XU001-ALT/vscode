"""聊天面板：消息渲染、用户输入管道（含 Self-Correction 和多轮上下文）。"""
import streamlit as st
from core.session_state import ensure_defaults, set_llm_call_result
from core.chat_history import append_message, get_history
from core.translations import t
from ai.text_to_sql import to_sql_with_correction
from db.executor import execute_sql_safe


def _get_effective_model_name() -> str:
    try:
        from core.secrets import get_effective_model
        model = get_effective_model()
        if model:
            return model
    except Exception:
        pass
    try:
        from config import config
        return config.LLM_MODEL or t("default_model")
    except Exception:
        return t("default_model")


def _run_pipeline(query: str):
    schema_summary = st.session_state.get('orm_schema', '')
    if not schema_summary.strip():
        append_message('system', t("load_schema_first"))
        return

    history = get_history()
    model_name = _get_effective_model_name()

    try:
        sql, df, error = to_sql_with_correction(
            schema_summary=schema_summary,
            chat_history=history,
            user_query=query,
            execute_fn=execute_sql_safe,
        )
    except Exception as e:
        st.session_state['last_sql'] = None
        st.session_state['last_df'] = None
        error_detail = str(e)

        try:
            from core.secrets import sanitize_error
            error_detail = sanitize_error(error_detail)
        except ImportError:
            pass

        set_llm_call_result(success=False, model=model_name, error=error_detail[:80])

        if '401' in error_detail or 'Authorization' in error_detail or 'Unauthorized' in error_detail:
            hint = t("key_invalid")
        elif 'timeout' in error_detail.lower() or 'timed out' in error_detail.lower():
            hint = t("timeout")
        elif 'Connection' in error_detail or 'connect' in error_detail.lower():
            hint = t("conn_err")
        else:
            hint = t("sys_err") + error_detail
        append_message('assistant', hint)
        return

    set_llm_call_result(success=True, model=model_name)
    st.session_state['last_sql'] = sql

    if error:
        st.session_state['last_df'] = None
        append_message('assistant', (
            t("query_fail") + error +
            t("query_fail_hint")
        ), sql=sql)
    else:
        st.session_state['last_df'] = df
        row_count = len(df) if df is not None else 0
        append_message('assistant', t("rows_returned") + str(row_count) + t("rows_unit"), sql=sql)
        st.session_state['result_tabs'] = t("tab_chart")
        try:
            from ai.chart_recommendation import recommend_chart
            rec = recommend_chart(df, query, sql)
            st.session_state['chart_recommendation'] = rec
            if rec:
                st.session_state['_rec_gen'] = st.session_state.get('_rec_gen', 0) + 1
        except Exception:
            st.session_state['chart_recommendation'] = None


def _submit_query(query: str):
    query = query.strip()
    if not query:
        return
    with st.chat_message("user"):
        st.markdown(query)
    append_message('user', query)
    _run_pipeline(query)
    st.rerun()


def render():
    ensure_defaults()

    st.markdown(f'<p class="chat-title">{t("chat_title")}</p>', unsafe_allow_html=True)

    # 输入框固定在顶部
    with st.container(key="chat_input_area"):
        query = st.text_input(
            t("query"),
            key="chat_query_input",
            placeholder=t("query_ph"),
            label_visibility="collapsed",
        )
        if st.button(t("send"), key="send_btn", use_container_width=True):
            if query and query.strip():
                _submit_query(query.strip())

    # 聊天消息区域（flex:1 撑满剩余空间，溢出滚动）
    with st.container(key="chat_messages_area"):
        history = get_history()
        for msg in history[-2:]:
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
