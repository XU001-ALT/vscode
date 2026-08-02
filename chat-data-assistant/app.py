import streamlit as st
from ui import render_sidebar, render_chat_panel, render_result_panel
from db.connection import db_manager
from db.executor import fetch_full_schema
from schema.loader import load_from_text
from schema.validator import validate_schema
from schema.summarizer import summarize_schema

st.set_page_config(page_title="hydrogen-chat", page_icon=" H₂", layout="wide")

# 启动时自动连接数据库
@st.cache_resource
def init_db():
    try:
        db_manager.connect()
        return True
    except Exception:
        return False

db_connected = init_db()

st.markdown("""
<style>
    :root {
        --bg-color: #0e1424;
        --card-bg: rgba(20, 30, 60, 0.6);
        --border-color: #1d4ed8;
        --text-color: #e6ebff;
        --highlight-color: #fbbf24;
        --nav-bg: #0b1120;
        --accent-blue: #60a5fa;
    }

    /* 主背景 - 深海蓝 */
    .stApp, [data-testid="stAppViewContainer"] {
        background-color: var(--bg-color);
    }

    /* 侧边栏背景 */
    .stSidebar, section[data-testid="stSidebar"] {
        background-color: var(--nav-bg);
    }
    .stSidebar [data-testid="stMarkdown"] {
        color: var(--text-color);
    }

    /* 顶部 header */
    header {
        background-color: var(--nav-bg) !important;
        border-bottom: 1px solid #1e293b;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
    }
    header * {
        color: white !important;
    }

    /* 全局文字颜色 */
    .stMarkdown, .stMarkdown p, .stMarkdown li, label, .stLabel {
        color: var(--text-color) !important;
    }

    /* 标题和子标题 */
    h1, h2, h3, h4, h5, h6, [data-testid="stMarkdownContainer"] h1,
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3 {
        color: #fff !important;
    }

    /* 主标题 - 卡片化 + 科技角标 */
    .main-title {
        font-size: 2rem !important;
        font-weight: 700 !important;
        color: #fff;
        background: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 4px;
        padding: 14px 20px;
        position: relative;
        letter-spacing: 1px;
        margin-bottom: 0.5rem;
    }
    .main-title::before, .main-title::after {
        content: '';
        position: absolute;
        width: 12px;
        height: 12px;
        border: 2px solid var(--accent-blue);
    }
    .main-title::before { top: -1px; left: -1px; border-right: none; border-bottom: none; }
    .main-title::after { bottom: -1px; right: -1px; border-left: none; border-top: none; }

    /* Section 标题 - 卡片头风格 */
    .section-header {
        color: #fff !important;
        font-size: 1rem;
        font-weight: 600;
        text-align: center;
        padding: 10px 15px;
        background: rgba(30, 58, 138, 0.3);
        border: 1px solid var(--border-color);
        border-radius: 4px;
        margin: 16px 0 12px 0;
    }

    /* 侧边栏标题 */
    .sidebar-title {
        color: #fff !important;
        font-size: 1.2rem;
        font-weight: 700;
        padding-bottom: 8px;
        border-bottom: 2px solid rgba(29, 78, 216, 0.4);
        margin-bottom: 16px;
    }

    .sidebar-section {
        color: var(--accent-blue) !important;
        font-size: 0.95rem;
        font-weight: 600;
        margin-top: 16px;
        margin-bottom: 8px;
    }

    /* 输入框标签 */
    label, .stLabel, [data-testid="stWidgetLabel"] {
        color: #94a3b8 !important;
        font-weight: 500;
    }

    /* 隐藏 deploy 按钮 */
    .stDeployButton {
        display: none;
    }

    /* 聊天输入框 */
    div[data-testid="stChatInput"],
    .stChatInput,
    textarea[aria-label="Chat input"] {
        border: 2px solid var(--border-color) !important;
        border-radius: 4px !important;
        background-color: var(--card-bg) !important;
        color: var(--text-color) !important;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
        margin-bottom: 16px;
    }
    div[data-testid="stChatInput"]:focus-within {
        border-color: var(--accent-blue) !important;
        box-shadow: 0 2px 12px rgba(96, 165, 250, 0.3);
    }

    /* 聊天气泡 - 用户消息（卡片化） */
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
        background-color: rgba(30, 58, 138, 0.35);
        border: 1px solid rgba(29, 78, 216, 0.4);
        border-radius: 4px;
        padding: 12px;
        margin: 8px 0;
    }

    /* 聊天气泡 - 助手消息（卡片化） */
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
        background-color: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 4px;
        padding: 12px;
        margin: 8px 0;
    }

    /* 按钮样式 */
    .stButton > button {
        background-color: var(--accent-blue);
        color: #0b1120;
        border: none;
        border-radius: 4px;
        font-weight: 600;
    }
    .stButton > button:hover {
        background-color: #93c5fd;
    }

    /* 输入框和选择框 */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div,
    .stMultiSelect > div > div {
        background-color: var(--card-bg) !important;
        color: var(--text-color) !important;
        border-color: var(--border-color) !important;
    }

    /* 信息/警告/错误提示框 */
    .stAlert {
        background-color: var(--card-bg);
        border-color: var(--border-color);
        color: var(--text-color);
    }

    /* 代码块 */
    .stCode {
        background-color: var(--card-bg);
    }

    /* 数据表格 */
    .stDataFrame {
        background-color: var(--card-bg);
    }

    /* 分割线 */
    hr {
        border-color: rgba(29, 78, 216, 0.3);
    }

    /* 小标签/提示文字 */
    .small-label {
        color: #64748b;
        font-size: 0.85rem;
    }

    /* 数字高亮 - 琥珀金 */
    .highlight {
        color: var(--highlight-color);
        font-weight: bold;
        text-shadow: 0 0 10px rgba(251, 191, 36, 0.4);
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">hydrogen-chat</p>', unsafe_allow_html=True)

if not db_connected:
    st.warning("数据库连接失败，请检查 .env 中的配置")

# 连接成功后自动拉取 Schema（仅首次，不覆盖手动加载）
if db_connected and not st.session_state.get('orm_schema'):
    try:
        raw_text = fetch_full_schema()
        tables = load_from_text(raw_text)
        ok, _ = validate_schema(tables)
        if ok:
            st.session_state['orm_schema'] = summarize_schema(tables)
            st.session_state['orm_schema_tables'] = [t.name for t in tables]
    except Exception:
        st.session_state['orm_auto_failed'] = True

with st.sidebar:
    render_sidebar()

with st.container():
    render_chat_panel()

with st.container():
    render_result_panel()

if __name__ == '__main__':
    pass
