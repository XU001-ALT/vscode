# session_state 辅助函数
import streamlit as st


def ensure_defaults():
    if 'messages' not in st.session_state:
        st.session_state['messages'] = []
    if 'orm_schema' not in st.session_state:
        st.session_state['orm_schema'] = ''
    if 'last_sql' not in st.session_state:
        st.session_state['last_sql'] = None
    if 'last_df' not in st.session_state:
        st.session_state['last_df'] = None
    if 'chart_type' not in st.session_state:
        st.session_state['chart_type'] = 'line'
    # 用户自定义 LLM 配置
    # 注意: API Key 不在 session_state 中存储明文，而是通过 core.secrets 服务端私有存储
    # 仅保留 token 引用和 UI 辅助字段
    if 'llm_provider' not in st.session_state:
        st.session_state['llm_provider'] = ''
    if 'llm_base_url' not in st.session_state:
        st.session_state['llm_base_url'] = ''
    if 'llm_model' not in st.session_state:
        st.session_state['llm_model'] = ''

    # API 调用状态追踪（供 sidebar 动态状态栏使用）
    if '_llm_call_status' not in st.session_state:
        st.session_state['_llm_call_status'] = None   # None | 'success' | 'error'
    if '_llm_call_model' not in st.session_state:
        st.session_state['_llm_call_model'] = ''       # 上次成功调用的模型名
    if '_llm_call_error' not in st.session_state:
        st.session_state['_llm_call_error'] = ''        # 上次调用的错误信息（简短）


_CHART_WIDGET_KEYS = (
    'chart_x', 'chart_y', 'chart_type_selector', 'use_auto_chart',
    'pie_names', 'pie_values', 'chart_type',
)

_API_INPUT_KEYS = (
    'llm_api_key_input',   # 密码输入框的值（敏感，清除后不留痕迹）
)


def set_llm_call_result(success: bool, model: str = "", error: str = ""):
    """记录最近一次 LLM 调用结果，供 sidebar 动态状态栏使用。"""
    st = __import__('streamlit')
    st.session_state['_llm_call_status'] = 'success' if success else 'error'
    st.session_state['_llm_call_model'] = model
    st.session_state['_llm_call_error'] = error[:120] if error else ''


def clear_session():
    """重置会话：清空聊天记录、查询结果、图表控件与 Tab 状态。

    注意：不清除 LLM 配置（Base URL / Model / 密钥令牌），
    因为这些是用户手动填入的，频繁清空体验很差。
    但会清除密码输入框中的明文残留。
    """
    st.session_state['messages'] = []
    st.session_state['last_sql'] = None
    st.session_state['last_df'] = None
    st.session_state['chart_recommendation'] = None
    st.session_state['result_tabs'] = '数据预览'
    st.session_state['_chart_cols_key'] = None
    st.session_state['_rec_gen'] = None
    st.session_state['_seen_rec_gen'] = None
    # 重置 API 调用状态
    st.session_state['_llm_call_status'] = None
    st.session_state['_llm_call_model'] = ''
    st.session_state['_llm_call_error'] = ''
    for k in _CHART_WIDGET_KEYS:
        st.session_state.pop(k, None)
    # 清除密码输入框明文残留（密钥本身在服务端私有存储中，不受影响）
    for k in _API_INPUT_KEYS:
        st.session_state.pop(k, None)
