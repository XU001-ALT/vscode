import streamlit as st
from ui import sidebar, chat_panel, result_panel

st.set_page_config(page_title="数据库智能绘图助手", layout="wide")

st.title("数据库智能绘图助手（MVP）")

with st.sidebar:
    sidebar.render()

with st.container():
    chat_panel.render()

with st.container():
    result_panel.render()

if __name__ == '__main__':
    pass
