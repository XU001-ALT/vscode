"""应用引导模块：启动即后台连接数据库并自动拉取 schema。

连接失败会持续自动重试（默认每 5 秒一次）；连接成功后保持连接复用，
仅对 schema 重试，不再反复断开重建连接，避免数据库出现无谓的连接抖动。
"""
import threading
import time

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from db.connection import db_manager
from db.executor import fetch_full_schema
from schema.loader import load_from_text
from schema.validator import validate_schema
from schema.summarizer import summarize_schema

RETRY_INTERVAL = 5.0

_lock = threading.Lock()
_state = {
    "connected": False,   # 是否已成功连上数据库
    "done": False,        # 是否已完成连接 + schema 拉取
    "schema": "",         # 自动拉取并裁剪的 schema 文本
    "tables": [],         # 表名列表
    "attempts": 0,        # 已尝试次数
    "last_error": "",     # 最近一次失败原因（供 UI 展示）
}
_started = False


def _try_connect() -> bool:
    """建立数据库连接并探测可用性。成功置 connected=True，返回 True。"""
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
            _state["last_error"] = str(e)
        return False
    with _lock:
        _state["connected"] = True
        _state["last_error"] = ""
    return True


def _try_fetch_schema() -> bool:
    """在已连接的基础上拉取并解析 schema。

    - 成功：置 done=True，缓存 schema / tables。
    - 连接层错误（OperationalError）：连接已断，关闭并标记未连接，下次重连。
    - 解析类错误：仅记录 last_error，保留连接，避免反复断开重建。
    """
    try:
        raw = fetch_full_schema()
        tables = load_from_text(raw)
        ok, _ = validate_schema(tables)
        if not ok:
            raise ValueError("schema 解析失败")
    except OperationalError as e:
        db_manager.close()
        with _lock:
            _state["connected"] = False
            _state["last_error"] = str(e)
        return False
    except Exception as e:
        with _lock:
            _state["last_error"] = str(e)
        return False

    with _lock:
        _state["done"] = True
        _state["schema"] = summarize_schema(tables)
        _state["tables"] = [t.name for t in tables]
        _state["last_error"] = ""
    return True


def _worker():
    while True:
        if _state["done"]:
            return
        if not _state["connected"]:
            if not _try_connect():
                time.sleep(RETRY_INTERVAL)
                continue
        if _try_fetch_schema():
            return
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
