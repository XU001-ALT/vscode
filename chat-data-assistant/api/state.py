"""全局共享状态：当前生效的 schema（自动拉取或手动上传）。"""
import threading

_lock = threading.Lock()
_state = {
    "schema": "",    # 裁剪后的 schema 文本（注入 prompt 用）
    "tables": [],    # 表名列表
}


def set_schema(schema: str, tables: list[str]) -> None:
    with _lock:
        _state["schema"] = schema
        _state["tables"] = tables


def get_schema() -> tuple[str, list[str]]:
    with _lock:
        return _state["schema"], list(_state["tables"])
