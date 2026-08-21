"""服务端会话存储：多轮对话上下文 + LLM 配置。

API Key 只保留在服务端内存中，前端仅拿到脱敏后的展示信息，
彻底避免 Streamlit 时代 session_state 经 WebSocket 序列化到浏览器的泄漏风险。
"""
import secrets as _secrets
import threading

_lock = threading.Lock()
_sessions: dict[str, dict] = {}


def _new_session() -> dict:
    return {
        "messages": [],   # [{"role", "content", "sql"}]，供多轮 prompt 使用
        "llm": {
            "provider": "",
            "base_url": "",
            "model": "",
            "api_key": "",
        },
    }


def create() -> str:
    sid = _secrets.token_hex(12)
    with _lock:
        _sessions[sid] = _new_session()
    return sid


def get(session_id: str) -> dict:
    with _lock:
        s = _sessions.get(session_id)
        if s is None:
            s = _new_session()
            _sessions[session_id] = s
        return s


def append_message(session_id: str, role: str, content: str, **meta) -> None:
    s = get(session_id)
    with _lock:
        msg = {"role": role, "content": content}
        msg.update(meta)
        s["messages"].append(msg)


def get_history(session_id: str) -> list[dict]:
    with _lock:
        return [dict(m) for m in get(session_id)["messages"]]


def set_llm_config(session_id: str, provider: str | None = None,
                   base_url: str | None = None, model: str | None = None,
                   api_key: str | None = None) -> None:
    """更新会话级 LLM 配置；传 None 表示保持不变，传空字符串表示清除。"""
    s = get(session_id)
    with _lock:
        if provider is not None:
            s["llm"]["provider"] = provider.strip().lower()
        if base_url is not None:
            s["llm"]["base_url"] = base_url.strip()
        if model is not None:
            s["llm"]["model"] = model.strip()
        if api_key is not None:
            s["llm"]["api_key"] = api_key.strip()


def clear_llm_config(session_id: str) -> None:
    s = get(session_id)
    with _lock:
        s["llm"] = {"provider": "", "base_url": "", "model": "", "api_key": ""}
