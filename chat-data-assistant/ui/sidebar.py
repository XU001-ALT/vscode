import streamlit as st
from config import config
from core.session_state import ensure_defaults
from core import bootstrap
from core.translations import t
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
    key_value = st.session_state.get("llm_api_key_input", "").strip()
    old_token = st.session_state.get(TOKEN_KEY, "")

    if key_value:
        token = secrets_store(key_value)
        st.session_state[TOKEN_KEY] = token
        st.session_state[HAS_CUSTOM_KEY] = True
    elif old_token:
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
    tables = load_from_text(raw_text)
    ok, errors = validate_schema(tables)
    if not ok:
        st.error(t("schema_err") + "; ".join(errors))
        return False
    processed = summarize_schema(tables)
    st.session_state['orm_schema'] = processed
    st.session_state['orm_schema_tables'] = [t_item.name for t_item in tables]
    return True


def _render_connected(info: dict):
    st.success(f"{t('db_connected')}: {info['database']}")
    st.caption(f"PostgreSQL {info['version']}")

def _render_connecting():
    st.info(t("db_connecting"))

def _render_db_status():
    state = bootstrap.get_state()
    if state["connected"]:
        try:
            info = db_manager.get_info()
        except Exception:
            info = None
        if info:
            _render_connected(info)
        else:
            st.success(t("db_connected"))
    elif state["last_error"]:
        st.error(t("db_failed") + ": " + state["last_error"])
    else:
        _render_connecting()


def render():
    ensure_defaults()
    st.markdown(f'<p class="sidebar-title">{t("schema_mgmt")}</p>', unsafe_allow_html=True)
    _render_db_status()

    # ── API 配置 ──
    with st.expander(t("api_config"), expanded=False):
        st.caption(t("api_config_hint"))

        if TOKEN_KEY not in st.session_state:
            st.session_state[TOKEN_KEY] = ""
        if HAS_CUSTOM_KEY not in st.session_state:
            st.session_state[HAS_CUSTOM_KEY] = False

        try:
            preset_idx = _CUSTOM_INDEX
            label = st.selectbox(
                t("model_select"),
                _PRESET_LABELS,
                index=preset_idx,
                key="model_preset_sel",
                on_change=_on_preset_change,
            )
        except Exception:
            label = st.selectbox(
                t("model_select"),
                _PRESET_LABELS,
                key="model_preset_sel",
                on_change=_on_preset_change,
            )

        st.text_input(
            "API Base URL",
            key="llm_base_url",
            placeholder="https://api.deepseek.com",
        )

        key_is_stored = bool(st.session_state.get(HAS_CUSTOM_KEY))

        st.text_input(
            "API Key",
            key="llm_api_key_input",
            type="password",
            placeholder="sk-..." if not key_is_stored else f"••••••••（{t('key_set')}）",
            on_change=_on_key_input,
        )

        old_legacy_key = st.session_state.get("llm_api_key", "").strip()
        if old_legacy_key and not key_is_stored:
            token = secrets_store(old_legacy_key)
            st.session_state[TOKEN_KEY] = token
            st.session_state[HAS_CUSTOM_KEY] = True
            st.session_state["llm_api_key"] = ""

        if key_is_stored:
            from core.secrets import retrieve, mask_key
            token = st.session_state.get(TOKEN_KEY, "")
            actual_key = retrieve(token)
            col1, col2 = st.columns([3, 1])
            with col1:
                st.caption(f"{t('current_key')}：{mask_key(actual_key)}")
            with col2:
                if st.button(t("clear"), key="clear_key_btn"):
                    secrets_remove(token)
                    st.session_state[TOKEN_KEY] = ""
                    st.session_state[HAS_CUSTOM_KEY] = False
                    st.session_state["llm_api_key_input"] = ""
                    st.rerun()

        st.text_input(
            t("model_name"),
            key="llm_model",
            placeholder=t("model_name_ph"),
        )

        call_status = st.session_state.get('_llm_call_status')
        call_model = st.session_state.get('_llm_call_model', '')
        call_error = st.session_state.get('_llm_call_error', '')

        if not key_is_stored and not config.LLM_API_KEY:
            st.warning(t("no_api_key"))
        elif call_status == 'success':
            model_display = call_model or st.session_state.get('llm_model', '') or t("default_model")
            st.success(t("call_ok") + model_display)
        elif call_status == 'error':
            error_brief = call_error[:50] + ('...' if len(call_error) > 50 else '')
            st.error(t("call_fail") + error_brief)
        elif key_is_stored:
            model_display = st.session_state.get('llm_model', '') or t("default_model")
            st.info(t("custom_model_info") + model_display + t("awaiting_call"))
        else:
            st.info(t("using_default"))

    st.markdown("---")
    st.markdown(f'<p class="sidebar-section">{t("data_guide")}</p>', unsafe_allow_html=True)
    tables = st.session_state.get('orm_schema_tables', [])
    if tables:
        with st.expander(t("table_desc"), expanded=False):
            desc = load_descriptions()
            for tbl in tables:
                d = desc.get(tbl, "")
                if d:
                    st.markdown(f"**{tbl}** — {d}")
                else:
                    st.markdown(f"**{tbl}**")
    else:
        st.caption(t("load_schema_hint"))

    st.markdown("---")
    st.markdown(f'<p class="sidebar-section">{t("load_schema")}</p>', unsafe_allow_html=True)

    schema_loaded = bool(st.session_state.get('orm_schema_tables'))

    if not schema_loaded:
        if st.button(t("fetch_schema")):
            with st.spinner(t("fetching")):
                try:
                    raw_text = fetch_full_schema()
                    if _process_schema(raw_text):
                        n = len(st.session_state.get('orm_schema_tables', []))
                        st.success(t("loaded_n") + str(n) + t("tables_unit"))
                except Exception as e:
                    st.error(t("fetch_fail") + str(e))

    with st.expander(t("upload_schema"), expanded=not schema_loaded):
        uploaded = st.file_uploader(t("upload_hint"), type=["py", "json", "txt"], key="orm_uploader")
        if uploaded is not None:
            try:
                content = uploaded.getvalue().decode('utf-8')
            except Exception:
                content = str(uploaded.getvalue())
            if _process_schema(content):
                n = len(st.session_state.get('orm_schema_tables', []))
                st.success(t("loaded_n") + str(n) + t("tables_unit"))
