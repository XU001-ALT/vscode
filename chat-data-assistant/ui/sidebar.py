import streamlit as st
from core.session_state import ensure_defaults


def render():
    ensure_defaults()
    st.header("配置 / ORM")
    st.subheader("数据库连接")
    st.text_input("Host", value=st.session_state.get('db_host', 'localhost'), key="db_host")
    st.text_input("Port", value=str(st.session_state.get('db_port', 5432)), key="db_port")
    st.text_input("数据库 名称", value=st.session_state.get('db_name', 'your_db'), key="db_name")
    st.text_input("数据库 用户", value=st.session_state.get('db_user', 'read_only'), key="db_user")
    st.text_input("数据库 密码", type="password", value=st.session_state.get('db_password', ''), key="db_password")
    if st.button("保存数据库配置"):
        st.success("已保存数据库配置到 session_state")

    st.markdown("---")
    st.subheader("ORM / Schema")
    uploaded = st.file_uploader("上传 ORM 文件（Python / JSON / TXT）", type=["py", "json", "txt"], key="orm_uploader")
    if uploaded is not None:
        try:
            content = uploaded.getvalue().decode('utf-8')
        except Exception:
            content = str(uploaded.getvalue())
        st.session_state['orm_schema'] = content
        st.success("已从文件加载并缓存 ORM 到 session_state['orm_schema']")

    st.text_area("粘贴或编辑 ORM/schema（仅需一次）", value=st.session_state.get('orm_schema', ''), key="orm_input", height=200)
    if st.button("确认并缓存 ORM"):
        st.session_state['orm_schema'] = st.session_state.get('orm_input', '')
        st.success("ORM 已缓存到 session_state['orm_schema']")

    st.markdown("---")
    st.subheader("状态")
    if st.session_state.get('orm_schema'):
        st.info("ORM 已加载到会话")
    else:
        st.warning("未加载 ORM：请粘贴或上传 schema 并点击确认")
