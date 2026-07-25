import streamlit as st
from core.session_state import ensure_defaults
from db.executor import fetch_full_schema
from db.connection import db_manager, DatabaseConfigError
from schema.loader import load_from_text
from schema.validator import validate_schema
from schema.summarizer import summarize_schema


def _get_db_config() -> dict:
    return {
        "host": st.session_state.get('db_host', 'localhost'),
        "port": int(st.session_state.get('db_port', 5432)),
        "dbname": st.session_state.get('db_name', ''),
        "user": st.session_state.get('db_user', ''),
        "password": st.session_state.get('db_password', ''),
    }


def _process_schema(raw_text: str) -> bool:
    """解析、校验、裁剪 schema，存入 session_state。返回是否成功"""
    tables = load_from_text(raw_text)
    ok, errors = validate_schema(tables)
    if not ok:
        st.error("Schema 校验失败: " + "; ".join(errors))
        return False
    processed = summarize_schema(tables)
    st.session_state['orm_schema'] = processed
    st.session_state['orm_schema_tables'] = [t.name for t in tables]
    return True


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
        try:
            cfg = _get_db_config()
            db_manager.connect_with_config(**cfg)
            st.success("数据库连接成功")
        except (DatabaseConfigError, Exception) as e:
            st.error(f"连接失败: {e}")

    st.markdown("---")
    st.subheader("ORM / Schema")
    if st.button("从数据库自动拉取 Schema"):
        with st.spinner("正在连接数据库并拉取表结构..."):
            try:
                cfg = _get_db_config()
                db_manager.connect_with_config(**cfg)
                raw_text = fetch_full_schema()
                if _process_schema(raw_text):
                    n = len(st.session_state.get('orm_schema_tables', []))
                    st.success(f"已拉取并处理 Schema，共 {n} 张表")
            except Exception as e:
                st.error(f"拉取失败: {e}")

    uploaded = st.file_uploader("上传 ORM 文件（Python / JSON / TXT）", type=["py", "json", "txt"], key="orm_uploader")
    if uploaded is not None:
        try:
            content = uploaded.getvalue().decode('utf-8')
        except Exception:
            content = str(uploaded.getvalue())
        if _process_schema(content):
            n = len(st.session_state.get('orm_schema_tables', []))
            st.success(f"已加载并处理 Schema，共 {n} 张表")

    st.text_area("粘贴或编辑 ORM/schema（仅需一次）", value=st.session_state.get('orm_schema', ''), key="orm_input", height=200)
    if st.button("确认并缓存 ORM"):
        raw = st.session_state.get('orm_input', '')
        if _process_schema(raw):
            n = len(st.session_state.get('orm_schema_tables', []))
            st.success(f"ORM 已缓存，共 {n} 张表")

    st.markdown("---")
    st.subheader("状态")
    tables = st.session_state.get('orm_schema_tables')
    if tables:
        st.info(f"已加载 {len(tables)} 张表: {', '.join(tables[:10])}{'...' if len(tables) > 10 else ''}")
    else:
        st.warning("未加载 ORM：请粘贴或上传 schema 并点击确认")
