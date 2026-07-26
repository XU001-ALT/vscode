import streamlit as st
from ui import sidebar, chat_panel, result_panel

st.set_page_config(page_title="氢问", page_icon=" H₂", layout="wide")

st.markdown("""
<style>
    /* 主背景 */
    .stApp, [data-testid="stAppViewContainer"] {
        background-color: #f0f2f6;
    }

    /* 侧边栏背景 */
    .stSidebar, section[data-testid="stSidebar"] {
        background-color: #e8edf3;
    }

    /* 顶部 header */
    header {
        background-color: #1a365d !important;
    }
    header * {
        color: white !important;
    }

    /* 隐藏 deploy 按钮 */
    .stDeployButton {
        display: none;
    }

    /* 聊天输入框（多选择器兜底） */
    div[data-testid="stChatInput"],
    .stChatInput,
    textarea[aria-label="Chat input"] {
        border: 2px solid #1a365d !important;
        border-radius: 12px !important;
        background-color: #ffffff !important;
        box-shadow: 0 2px 8px rgba(26, 54, 93, 0.15);
        margin-bottom: 16px;
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
