import streamlit as st
from core.session_state import ensure_defaults
from core import bootstrap
from db.executor import fetch_full_schema
from db.connection import db_manager
from schema.loader import load_from_text
from schema.validator import validate_schema
from schema.summarizer import summarize_schema
from schema.descriptions import load_descriptions


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


def _render_connected():
    """数据库已连接时展示详细信息（连接异常时降级为简单提示，不报错）"""
    try:
        info = db_manager.get_info()
        st.success(f"数据库已连接: {info['database']}")
        st.caption(f"PostgreSQL {info['version'][:20]}...")
    except Exception:
        st.success("数据库已连接")


@st.fragment(run_every=3)
def _render_connecting():
    """连接中：后台线程持续重试，这里每 3 秒自动刷新一次状态。

    连上后触发一次整页重跑，让 app.py 把自动拉取的 schema 同步进会话，
    并切换回静态的"已连接"状态（不再轮询）。
    """
    state = bootstrap.get_state()
    if state.get("done"):
        st.rerun(scope="app")
    else:
        st.info("正在连接数据库，系统自动重试中…")
        if state.get("last_error"):
            st.caption(f"最近一次失败：{state['last_error'][:120]}")


def _render_db_status():
    """数据库连接状态（后台自动重连，成功后自动刷新，用户无感）"""
    if bootstrap.get_state().get("done"):
        _render_connected()
    else:
        _render_connecting()


def render():
    ensure_defaults()
    st.markdown('<p class="sidebar-title">Schema 管理</p>', unsafe_allow_html=True)

    _render_db_status()

    st.markdown("---")
    st.markdown('<p class="sidebar-section">数据使用说明</p>', unsafe_allow_html=True)
    tables = st.session_state.get('orm_schema_tables', [])
    if tables:
        with st.expander("各表数据含义（点击展开）", expanded=False):
            desc = load_descriptions()
            for t in tables:
                d = desc.get(t, "")
                if d:
                    st.markdown(f"**{t}** — {d}")
                else:
                    st.markdown(f"**{t}**")
    else:
        st.caption("加载 Schema 后可查看各表对应的数据含义")

    st.markdown("---")
    st.markdown('<p class="sidebar-section">加载 Schema</p>', unsafe_allow_html=True)

    schema_loaded = bool(st.session_state.get('orm_schema_tables'))

    if schema_loaded:
        tables = st.session_state.get('orm_schema_tables', [])
        st.success(f"Schema 已加载，共 {len(tables)} 张表")
    else:
        if st.button("从数据库拉取 Schema"):
            with st.spinner("正在拉取表结构..."):
                try:
                    raw_text = fetch_full_schema()
                    if _process_schema(raw_text):
                        n = len(st.session_state.get('orm_schema_tables', []))
                        st.success(f"已拉取并处理 Schema，共 {n} 张表")
                except Exception as e:
                    st.error(f"拉取失败: {e}")

    with st.expander("编辑 / 重新加载 Schema（仅需一次）", expanded=not schema_loaded):
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
    st.markdown('<p class="sidebar-section">状态</p>', unsafe_allow_html=True)
    tables = st.session_state.get('orm_schema_tables')
    if tables:
        st.info(f"已加载 {len(tables)} 张表: {', '.join(tables[:10])}{'...' if len(tables) > 10 else ''}")
    else:
        st.info("未加载 ORM：请粘贴或上传 schema 并点击确认")
