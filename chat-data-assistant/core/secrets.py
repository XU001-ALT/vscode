"""服务端私有密钥存储。

Streamlit 的 st.session_state 会通过 WebSocket 序列化到浏览器（包括 type="password" 的输入值），
这意味着用户的 API Key 有泄漏风险。

本模块使用服务端全局字典存储密钥，只往 session_state 放一个令牌引用。
前端始终只能拿到令牌，无法反查真实 Key。
"""
import secrets as _secrets
import threading
from typing import Optional

from config import config

# 服务端私有存储（不进入 WebSocket 序列化）
_store: dict[str, dict] = {}
_lock = threading.Lock()

# session_state 中存储的令牌 key 名
TOKEN_KEY = "_api_key_token"
# session_state 中标记"已设置自定义 Key"的 key 名
HAS_CUSTOM_KEY = "_has_custom_api_key"


def _generate_token() -> str:
    """生成加密安全的随机令牌（48 字符 hex）。"""
    return _secrets.token_hex(24)


def store(api_key: str) -> str:
    """将 API Key 存入服务端私有存储，返回令牌。

    调用方（sidebar）把返回的令牌写入 st.session_state[TOKEN_KEY]。
    """
    token = _generate_token()
    with _lock:
        _store[token] = {
            "api_key": api_key,
        }
    return token


def retrieve(token: str | None = None) -> str:
    """通过令牌取回 API Key（服务端内存，绝不会到达浏览器）。

    返回空字符串表示令牌无效或过期。
    """
    if not token:
        return ""
    with _lock:
        entry = _store.get(token)
    return entry["api_key"] if entry else ""


def remove(token: str | None = None) -> None:
    """清除指定令牌对应的 Key。"""
    if not token:
        return
    with _lock:
        _store.pop(token, None)


def get_effective_key() -> str:
    """获取当前生效的 API Key。

    优先级: 侧边栏用户输入（通过服务端私有存储） > .env 配置
    """
    try:
        import streamlit as st
        token = st.session_state.get(TOKEN_KEY, "")
        if token:
            key = retrieve(token)
            if key:
                return key
        # 回退：检查 session_state 中是否有直接设置的 key（兼容旧代码）
        direct_key = st.session_state.get("llm_api_key", "").strip()
        if direct_key:
            return direct_key
    except Exception:
        pass
    return config.LLM_API_KEY


def get_effective_base_url() -> str:
    """获取当前生效的 API Base URL。"""
    try:
        import streamlit as st
        url = st.session_state.get("llm_base_url", "").strip()
        if url:
            return url
    except Exception:
        pass
    return config.LLM_BASE_URL


def get_effective_model() -> str:
    """获取当前生效的模型名。"""
    try:
        import streamlit as st
        model = st.session_state.get("llm_model", "").strip()
        if model:
            return model
    except Exception:
        pass
    return config.LLM_MODEL


def mask_key(key: str, visible: int = 6) -> str:
    """脱敏展示 API Key：sk-b64d...8ad。

    只保留首尾各 visible 个字符，其余用 * 替代。
    长度不足时不脱敏（直接返回原值）。
    """
    if not key or len(key) <= visible * 2 + 2:
        return key
    return f"{key[:visible]}***{key[-visible:]}"


def sanitize_error(error_text: str) -> str:
    """过滤错误消息中的敏感信息（API Key、Bearer token 等）。

    匹配模式：
    - sk- 开头的密钥
    - Bearer 后面的 token
    - 其他常见 API Key 格式
    """
    import re

    # 获取当前 key 做精确替换
    current_key = get_effective_key()
    if current_key and current_key in error_text:
        error_text = error_text.replace(current_key, mask_key(current_key))

    # 通用模式：sk- 开头 + 字母数字的密钥
    error_text = re.sub(r'sk-[a-zA-Z0-9]{16,}', '[API_KEY_REDACTED]', error_text)
    # Bearer token
    error_text = re.sub(r'Bearer\s+[a-zA-Z0-9\-_=+]{16,}', 'Bearer [REDACTED]', error_text)

    return error_text
