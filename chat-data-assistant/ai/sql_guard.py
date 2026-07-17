# 简单的 SQL 白名单/黑名单检查

def is_select_only(sql_text):
    stripped = sql_text.strip().lower()
    return stripped.startswith('select')


def validate_sql(sql_text):
    if not is_select_only(sql_text):
        return False, "Only SELECT statements are allowed"
    return True, None
