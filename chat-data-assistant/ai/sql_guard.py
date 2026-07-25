# 简单的 SQL 白名单/黑名单检查

ALLOWED_PREFIXES = ("select", "with", "explain", "show", "describe", "desc")


def is_readonly(sql_text):
    stripped = sql_text.strip().lower()
    return any(stripped.startswith(p) for p in ALLOWED_PREFIXES)


def validate_sql(sql_text):
    if not sql_text or not sql_text.strip():
        return False, "SQL 不能为空"
    if not is_readonly(sql_text):
        return False, "仅允许 SELECT/WITH/EXPLAIN 等只读查询"
    return True, None
