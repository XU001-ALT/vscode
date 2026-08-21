"""服务端会话存储（SQLite）。

使用进程外共享的 SQLite 文件，多 uvicorn worker 下会话与多轮上下文保持一致。
API Key 只保留在服务端，前端仅拿到脱敏后的展示信息。
"""
import json
import secrets as _secrets
import sqlite3
import threading
from pathlib import Path

_DB_DIR = Path(__file__).resolve().parent.parent / "data"
_DB_PATH = _DB_DIR / "sessions.sqlite3"

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _DB_DIR.mkdir(exist_ok=True)
        conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS sessions ("
            " session_id TEXT PRIMARY KEY,"
            " data TEXT NOT NULL,"
            " updated_at REAL NOT NULL)"
        )
        conn.commit()
        _conn = conn
    return _conn


def _new_session() -> dict:
    return {
        "messages": [],   # [{"role", "content", "sql"}]，供多轮 prompt 使用
        "llm": {"provider": "", "base_url": "", "model": "", "api_key": ""},
    }


def _read(conn: sqlite3.Connection, sid: str) -> dict | None:
    row = conn.execute(
        "SELECT data FROM sessions WHERE session_id = ?", (sid,)
    ).fetchone()
    return json.loads(row[0]) if row else None


def _write(conn: sqlite3.Connection, sid: str, data: dict) -> None:
    import time
    conn.execute(
        "INSERT INTO sessions (session_id, data, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(session_id) DO UPDATE SET data = excluded.data,"
        " updated_at = excluded.updated_at",
        (sid, json.dumps(data, ensure_ascii=False), time.time()),
    )
    conn.commit()


def create() -> str:
    sid = _secrets.token_hex(12)
    with _lock:
        conn = _get_conn()
        _write(conn, sid, _new_session())
    return sid


def get(session_id: str) -> dict:
    with _lock:
        conn = _get_conn()
        data = _read(conn, session_id)
        if data is None:
            data = _new_session()
            _write(conn, session_id, data)
        return data


def append_message(session_id: str, role: str, content: str, **meta) -> None:
    with _lock:
        conn = _get_conn()
        data = _read(conn, session_id) or _new_session()
        msg = {"role": role, "content": content}
        msg.update(meta)
        data["messages"].append(msg)
        _write(conn, session_id, data)


def get_history(session_id: str) -> list[dict]:
    with _lock:
        conn = _get_conn()
        data = _read(conn, session_id)
        return list(data["messages"]) if data else []


def set_llm_config(session_id: str, provider: str | None = None,
                   base_url: str | None = None, model: str | None = None,
                   api_key: str | None = None) -> None:
    """更新会话级 LLM 配置；传 None 表示保持不变，传空字符串表示清除。"""
    with _lock:
        conn = _get_conn()
        data = _read(conn, session_id) or _new_session()
        llm = data["llm"]
        if provider is not None:
            llm["provider"] = provider.strip().lower()
        if base_url is not None:
            llm["base_url"] = base_url.strip()
        if model is not None:
            llm["model"] = model.strip()
        if api_key is not None:
            llm["api_key"] = api_key.strip()
        _write(conn, session_id, data)


def clear_llm_config(session_id: str) -> None:
    with _lock:
        conn = _get_conn()
        data = _read(conn, session_id) or _new_session()
        data["llm"] = {"provider": "", "base_url": "", "model": "", "api_key": ""}
        _write(conn, session_id, data)
