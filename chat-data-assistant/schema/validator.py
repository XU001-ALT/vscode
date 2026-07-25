from schema.loader import Table


def validate_schema(tables: list[Table]) -> tuple[bool, list[str]]:
    """校验解析后的 schema，返回 (是否有效, 错误列表)"""
    errors = []

    if not tables:
        errors.append("未解析到任何表，请检查 schema 格式")
        return False, errors

    names_seen = set()
    for t in tables:
        if not t.name:
            errors.append("存在空表名")
        elif t.name in names_seen:
            errors.append(f"表名重复: {t.name}")
        names_seen.add(t.name)

        if not t.columns:
            errors.append(f"表 {t.name} 没有任何列")

    return len(errors) == 0, errors
