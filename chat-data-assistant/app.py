import streamlit as st
from ui import render_sidebar, render_chat_panel, render_result_panel, render_home, render_settings
from ui.navigation import render_navigation
from core import bootstrap
from core.translations import t
from ui.theme import apply_theme

st.set_page_config(page_title="chat-data", page_icon=" H₂", layout="wide")

bootstrap.start()

apply_theme()

# 语言切换 + 导航放在顶部一行
top_col1, top_col2, top_col3 = st.columns([8, 2, 1])

with top_col1:
    page = render_navigation()

with top_col3:
    current_lang = st.session_state.get('lang', 'zh')
    if st.button(t("lang_btn"), key="lang_toggle", help="Switch language"):
        st.session_state['lang'] = 'en' if current_lang == 'zh' else 'zh'
        st.rerun()

# 后台连接成功后，同步 Schema
if not st.session_state.get('orm_schema'):
    boot = bootstrap.get_state()
    if boot.get('schema'):
        st.session_state['orm_schema'] = boot['schema']
        st.session_state['orm_schema_tables'] = boot['tables']

st.markdown("---")

# 根据导航页面渲染内容
if page == "Home":
    render_home()
elif page == "AI Query":
    left_col, main_col = st.columns([2, 8], gap="medium")
    with left_col:
        render_sidebar()
    with main_col:
        query_col, result_col = st.columns([1, 1], gap="medium")
        with query_col:
            render_chat_panel()
        with result_col:
            render_result_panel()
elif page == "Settings":
    render_settings()

if __name__ == '__main__':
    pass
