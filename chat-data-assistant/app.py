import streamlit as st
from ui import sidebar, chat_panel, result_panel

st.set_page_config(page_title="氢问", page_icon=" H₂", layout="wide")

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
</style>
""", unsafe_allow_html=True)

st.title("氢问")

with st.sidebar:
    sidebar.render()

with st.container():
    chat_panel.render()

with st.container():
    result_panel.render()

if __name__ == '__main__':
    pass
