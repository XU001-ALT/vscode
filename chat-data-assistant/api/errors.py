"""错误分类：把后端错误消息映射为稳定错误码，前端按语言渲染文案。"""

_DB_MARKERS = (
    "ssl error", "connection refused", "could not connect", "connection reset",
    "server closed the connection", "operationalerror", "terminating connection",
    "connection timed out", "name or service not known", "getaddrinfo failed",
    "sql执行失败",
)


def classify_error(msg: str) -> str:
    m = (msg or "").lower()
    if "401" in m or "unauthorized" in m or "invalid api key" in m or "authorization" in m:
        return "llm_auth"
    if any(k in m for k in _DB_MARKERS):
        return "db_unreachable"
    if "timeout" in m or "timed out" in m:
        return "llm_timeout"
    if "合法 sql" in m or "valid sql" in m:
        return "no_valid_sql"
    if "无法连接" in m or "cannot connect" in m or "connection" in m or "connect" in m:
        return "llm_conn"
    return "unknown"
