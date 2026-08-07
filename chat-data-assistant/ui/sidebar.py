import streamlit as st
from config import config
from core.session_state import ensure_defaults
from core import bootstrap
from core.secrets import store as secrets_store, remove as secrets_remove, mask_key, TOKEN_KEY, HAS_CUSTOM_KEY
from db.executor import fetch_full_schema
from db.connection import db_manager
from schema.loader import load_from_text
from schema.validator import validate_schema
from schema.summarizer import summarize_schema
from schema.descriptions import load_descriptions

# ── 模型预设列表 ──
MODEL_PRESETS = [
    {"label": "DeepSeek V4 Flash",         "model": "deepseek-v4-flash",  "url": "https://api.deepseek.com"},
    {"label": "DeepSeek V4 Pro",           "model": "deepseek-v4-pro",    "url": "https://api.deepseek.com"},
    {"label": "GPT-4o Mini",               "model": "gpt-4o-mini",        "url": "https://api.openai.com"},
    {"label": "GPT-4o",                    "model": "gpt-4o",             "url": "https://api.openai.com"},
    {"label": "通义千问 Qwen-Plus",         "model": "qwen-plus",          "url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    {"label": "通义千问 Qwen-Max",          "model": "qwen-max",           "url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    {"label": "Moonshot Kimi",             "model": "moonshot-v1-8k",     "url": "https://api.moonshot.cn/v1"},
    {"label": "百川 Baichuan 4",           "model": "Baichuan4",          "url": "https://api.baichuan-ai.com/v1"},
    {"label": "自定义…",                   "model": "",                   "url": ""},
]

_PRESET_LABELS = [p["label"] for p in MODEL_PRESETS]
# "自定义…" 在列表中的索引
_CUSTOM_INDEX = len(MODEL_PRESETS) - 1


def _on_preset_change():
    """预设切换回调：自动填充 Model 和 URL，但不覆盖用户已编辑的内容。"""
    label = st.session_state.get("model_preset_sel", "")
    for p in MODEL_PRESETS:
        if p["label"] == label:
            if p["model"]:
                st.session_state["llm_model"] = p["model"]
            if p["url"]:
                st.session_state["llm_base_url"] = p["url"]
            break


def _on_key_input():
    """API Key 输入回调：同步到服务端私有存储。

    Streamlit 限制：密码输入框的值必须经过 session_state（WebSocket）。
    我们无法完全避免，但做了以下防护：
    1. 服务端存储是唯一权威来源（llm_client 从服务端读，不读 session_state）
    2. UI 中所有展示都用 mask_key() 脱敏
    3. 用户清空输入时同步清除服务端存储
    """
    key_value = st.session_state.get("llm_api_key_input", "").strip()
    old_token = st.session_state.get(TOKEN_KEY, "")

    if key_value:
        # 有输入 → 存入服务端，更新令牌
        token = secrets_store(key_value)
        st.session_state[TOKEN_KEY] = token
        st.session_state[HAS_CUSTOM_KEY] = True
    elif old_token:
        # 用户清空了输入框 → 清除服务端存储
        secrets_remove(old_token)
        st.session_state[TOKEN_KEY] = ""
        st.session_state[HAS_CUSTOM_KEY] = False


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

    # ── API 配置（用户自定义大模型） ──
    st.markdown("---")
    st.markdown('<p class="sidebar-section">API 配置</p>', unsafe_allow_html=True)
    st.caption("填写后使用你自己的大模型，费用由你承担；留空则使用系统默认配置。")

    # 初始化 session_state 中的令牌字段
    if TOKEN_KEY not in st.session_state:
        st.session_state[TOKEN_KEY] = ""
    if HAS_CUSTOM_KEY not in st.session_state:
        st.session_state[HAS_CUSTOM_KEY] = False

    # ── 模型预设选择 ──
    try:
        preset_idx = _CUSTOM_INDEX  # 默认"自定义…"
        label = st.selectbox(
            "模型选择",
            _PRESET_LABELS,
            index=preset_idx,
            key="model_preset_sel",
            on_change=_on_preset_change,
        )
    except Exception:
        label = st.selectbox(
            "模型选择",
            _PRESET_LABELS,
            key="model_preset_sel",
            on_change=_on_preset_change,
        )

    # ── API Base URL ──
    st.text_input(
        "API Base URL",
        key="llm_base_url",
        placeholder="https://api.deepseek.com",
    )

    # ── API Key（输入时经过 session_state，但 llm_client 从服务端私有存储读取，不依赖 session_state） ──
    key_is_stored = bool(st.session_state.get(HAS_CUSTOM_KEY))

    # 密钥输入框（密码模式，浏览器端显示为圆点）
    st.text_input(
        "API Key",
        key="llm_api_key_input",
        type="password",
        placeholder="sk-..." if not key_is_stored else "••••••••（已设置）",
        on_change=_on_key_input,
    )

    # 兼容旧代码：迁移以前存在 llm_api_key 中的值到新安全存储
    old_legacy_key = st.session_state.get("llm_api_key", "").strip()
    if old_legacy_key and not key_is_stored:
        token = secrets_store(old_legacy_key)
        st.session_state[TOKEN_KEY] = token
        st.session_state[HAS_CUSTOM_KEY] = True
        st.session_state["llm_api_key"] = ""

    # 清除按钮
    if key_is_stored:
        from core.secrets import retrieve, mask_key
        token = st.session_state.get(TOKEN_KEY, "")
        actual_key = retrieve(token)
        col1, col2 = st.columns([3, 1])
        with col1:
            st.caption(f"当前密钥：{mask_key(actual_key)}")
        with col2:
            if st.button("清除", key="clear_key_btn"):
                secrets_remove(token)
                st.session_state[TOKEN_KEY] = ""
                st.session_state[HAS_CUSTOM_KEY] = False
                st.session_state["llm_api_key_input"] = ""
                st.rerun()

    # ── 模型名称 ──
    st.text_input(
        "模型名称",
        key="llm_model",
        placeholder="留空自动选择（如 deepseek-v4-flash / gpt-4o-mini）",
    )

    # ── 动态状态栏 ──
    call_status = st.session_state.get('_llm_call_status')
    call_model = st.session_state.get('_llm_call_model', '')
    call_error = st.session_state.get('_llm_call_error', '')

    if not key_is_stored and not config.LLM_API_KEY:
        # 情况1: 完全没有配置任何 API Key
        st.warning("未配置 API Key，请填写 API Key 或检查 .env 文件")
    elif call_status == 'success':
        # 情况2: 调用成功
        model_display = call_model or st.session_state.get('llm_model', '') or '默认模型'
        st.success(f"✅ 调用成功 — {model_display}")
    elif call_status == 'error':
        # 情况3: 调用失败
        error_brief = call_error[:50] + ('...' if len(call_error) > 50 else '')
        st.error(f"❌ 调用失败 — {error_brief}")
    elif key_is_stored:
        # 情况4: 已配置自定义 Key，但尚未首次调用
        model_display = st.session_state.get('llm_model', '') or '默认模型'
        st.info(f"已配置自定义模型 {model_display}，等待首次调用")
    else:
        # 情况5: 使用 .env 默认配置，尚未调用
        st.info("当前使用默认模型")

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
