import streamlit as st
from ui import sidebar, chat_panel, result_panel

st.set_page_config(page_title="氢问", page_icon=" H₂", layout="wide")

st.markdown("""
<style>
    .stApp {
        background-color: #f0f2f6;
    }
    .stSidebar {
        background-color: #e8edf3;
    }
    header[data-testid="stHeader"] {
        background-color: #1a365d;
    }
    header[data-testid="stHeader"] * {
        color: white !important;
    }
    .stDeployButton {
        display: none;
    }
    div[data-testid="stChatInput"] {
        border: 2px solid #1a365d;
        border-radius: 12px;
        background-color: #ffffff;
        box-shadow: 0 2px 8px rgba(26, 54, 93, 0.15);
        margin-bottom: 16px;
    }
    div[data-testid="stChatInput"]:focus-within {
        border-color: #2c5282;
        box-shadow: 0 2px 12px rgba(26, 54, 93, 0.25);
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
