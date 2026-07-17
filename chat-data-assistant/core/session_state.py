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
    if 'chart_config' not in st.session_state:
        st.session_state['chart_config'] = {}
