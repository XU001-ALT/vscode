import streamlit as st
from ui import render_sidebar, render_chat_panel, render_result_panel
from db.connection import db_manager

st.set_page_config(page_title="氢问", page_icon=" H₂", layout="wide")

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
    /* 主背景 - 深色 */
    .stApp, [data-testid="stAppViewContainer"] {
        background-color: #0f172a;
    }

    /* 侧边栏背景 */
    .stSidebar, section[data-testid="stSidebar"] {
        background-color: #1e293b;
    }
    .stSidebar [data-testid="stMarkdown"] {
        color: #e2e8f0;
    }

    /* 顶部 header */
    header {
        background-color: #1e293b !important;
    }
    header * {
        color: white !important;
    }

    /* 全局文字颜色 */
    .stMarkdown, .stMarkdown p, .stMarkdown li, label, .stLabel {
        color: #e2e8f0 !important;
    }

    /* 标题和子标题 */
    h1, h2, h3, h4, h5, h6, [data-testid="stMarkdownContainer"] h1,
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3 {
        color: #f1f5f9 !important;
    }

    /* 主标题 - 渐变色 */
    .main-title {
        font-size: 2.5rem !important;
        font-weight: 700 !important;
        background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.5rem;
    }

    /* Section 标题样式 */
    .section-header {
        color: #38bdf8 !important;
        font-size: 1.1rem;
        font-weight: 600;
        padding: 8px 12px;
        background: linear-gradient(90deg, rgba(56, 189, 248, 0.15) 0%, transparent 100%);
        border-left: 3px solid #38bdf8;
        border-radius: 0 8px 8px 0;
        margin: 16px 0 12px 0;
    }

    /* 侧边栏标题 */
    .sidebar-title {
        color: #38bdf8 !important;
        font-size: 1.2rem;
        font-weight: 700;
        padding-bottom: 8px;
        border-bottom: 2px solid #334155;
        margin-bottom: 16px;
    }

    .sidebar-section {
        color: #7dd3fc !important;
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
        border: 2px solid #334155 !important;
        border-radius: 12px !important;
        background-color: #1e293b !important;
        color: #f1f5f9 !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        margin-bottom: 16px;
    }
    div[data-testid="stChatInput"]:focus-within {
        border-color: #38bdf8 !important;
        box-shadow: 0 2px 12px rgba(56, 189, 248, 0.3);
    }

    /* 聊天气泡 - 用户消息 */
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
        background-color: #1e3a5f;
        border-radius: 12px;
        padding: 12px;
        margin: 8px 0;
    }

    /* 聊天气泡 - 助手消息 */
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
        background-color: #1e293b;
        border-radius: 12px;
        padding: 12px;
        margin: 8px 0;
    }

    /* 按钮样式 */
    .stButton > button {
        background-color: #38bdf8;
        color: #0f172a;
        border: none;
        border-radius: 8px;
        font-weight: 600;
    }
    .stButton > button:hover {
        background-color: #7dd3fc;
    }

    /* 输入框和选择框 */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div,
    .stMultiSelect > div > div {
        background-color: #1e293b !important;
        color: #f1f5f9 !important;
        border-color: #334155 !important;
    }

    /* 信息/警告/错误提示框 */
    .stAlert {
        background-color: #1e293b;
        border-color: #334155;
        color: #e2e8f0;
    }

    /* 代码块 */
    .stCode {
        background-color: #1e293b;
    }

    /* 数据表格 */
    .stDataFrame {
        background-color: #1e293b;
    }

    /* 分割线 */
    hr {
        border-color: #334155;
    }

    /* 小标签/提示文字 */
    .small-label {
        color: #64748b;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">氢问 H₂</p>', unsafe_allow_html=True)

if not db_connected:
    st.warning("数据库连接失败，请检查 .env 中的配置")

with st.sidebar:
    render_sidebar()

with st.container():
    render_chat_panel()

with st.container():
    render_result_panel()

if __name__ == '__main__':
    pass
