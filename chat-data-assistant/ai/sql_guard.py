# 简单的 SQL 白名单/黑名单检查

import re

ALLOWED_PREFIXES = ("select", "with", "explain", "show", "describe", "desc")


def is_readonly(sql_text):
    stripped = sql_text.strip().lower()
    return any(stripped.startswith(p) for p in ALLOWED_PREFIXES)


def _strip_strings_and_comments(sql: str) -> str:
    """去掉字符串字面量、引号标识符与注释，避免内容中的分号干扰多语句判断。"""
    out = []
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if c == "'":  # 字符串字面量，'' 为转义
            i += 1
            while i < n:
                if sql[i] == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        i += 2
                        continue
                    break
                i += 1
            i += 1
        elif c == '"':  # 引号标识符
            i += 1
            while i < n and sql[i] != '"':
                i += 1
            i += 1
        elif sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j == -1 else j
        elif sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            i = n if j == -1 else j + 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def validate_sql(sql_text):
    if not sql_text or not sql_text.strip():
        return False, "SQL 不能为空"
    if not is_readonly(sql_text):
        return False, "仅允许 SELECT/WITH/EXPLAIN 等只读查询"

    # 多语句防护：'SELECT 1; DROP TABLE x' 这类语句不允许通过
    body = _strip_strings_and_comments(sql_text).strip()
    if body.endswith(";"):
        body = body[:-1].strip()
    if ";" in body:
        return False, "不允许一次执行多条 SQL 语句"
    return True, None
