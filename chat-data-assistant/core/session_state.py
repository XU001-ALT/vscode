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


_CHART_WIDGET_KEYS = (
    'chart_x', 'chart_y', 'chart_type_selector', 'use_auto_chart',
    'pie_names', 'pie_values', 'chart_type',
)


def clear_session():
    """重置会话：清空聊天记录、查询结果、图表控件与 Tab 状态。"""
    st.session_state['messages'] = []
    st.session_state['last_sql'] = None
    st.session_state['last_df'] = None
    st.session_state['chart_recommendation'] = None
    st.session_state['result_tabs'] = '数据预览'
    st.session_state['_chart_cols_key'] = None
    st.session_state['_rec_gen'] = None
    st.session_state['_seen_rec_gen'] = None
    for k in _CHART_WIDGET_KEYS:
        st.session_state.pop(k, None)
