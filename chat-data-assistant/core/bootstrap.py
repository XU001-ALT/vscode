"""应用引导模块：启动即后台连接数据库并自动拉取 schema。

连接失败会持续自动重试（默认每 5 秒一次），成功后把结果缓存在模块级
状态中供各页面读取，避免用户一打开页面就看到"数据库未连接"。
"""
import threading
import time

from sqlalchemy import text

from db.connection import db_manager
from db.executor import fetch_full_schema
from schema.loader import load_from_text
from schema.validator import validate_schema
from schema.summarizer import summarize_schema

RETRY_INTERVAL = 5.0

_lock = threading.Lock()
_state = {
    "connected": False,   # 是否已成功连上数据库
    "done": False,        # 是否已完成一次成功的连接（供 UI 判断）
    "schema": "",         # 自动拉取并裁剪的 schema 文本
    "tables": [],         # 表名列表
    "attempts": 0,        # 已尝试次数
    "last_error": "",     # 最近一次失败原因
}
_started = False


def _try_once() -> bool:
    """尝试连接数据库并拉取 schema。

    只有「连接成功 + schema 解析成功」才算成功；任一步失败都由外层
    循环重试（远程库偶发断连时保证最终能拿到完整 schema）。
    """
    with _lock:
        _state["attempts"] += 1
    try:
        engine = db_manager.connect()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_manager.close()
        with _lock:
            _state["connected"] = False
            _state["done"] = False
            _state["last_error"] = str(e)
        return False

    try:
        raw = fetch_full_schema()
        tables = load_from_text(raw)
        ok, _ = validate_schema(tables)
        if not ok:
            raise RuntimeError("schema 解析失败")
        with _lock:
            _state["connected"] = True
            _state["done"] = True
            _state["schema"] = summarize_schema(tables)
            _state["tables"] = [t.name for t in tables]
            _state["last_error"] = ""
        return True
    except Exception as e:
        # 连接成功但 schema 未就绪：清空状态，交由外层循环重试
        db_manager.close()
        with _lock:
            _state["connected"] = False
            _state["done"] = False
            _state["schema"] = ""
            _state["tables"] = []
            _state["last_error"] = str(e)
        return False


def _worker():
    while not _try_once():
        time.sleep(RETRY_INTERVAL)


def start():
    """幂等地启动后台连接线程（进程内只启动一次）。"""
    global _started
    with _lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_worker, name="db-bootstrap", daemon=True).start()


def get_state() -> dict:
    """返回当前连接/拉取状态（副本，线程安全）。"""
    with _lock:
        return dict(_state)
