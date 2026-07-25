from schema.loader import Table


def _estimate_tokens(text: str) -> int:
    """粗略估算 token 数（英文约 4 字符/token）"""
    return max(1, len(text) // 4)


def _format_full(table: Table) -> str:
    """完整格式：Table xxx:\n  col type"""
    lines = []
    for c in table.columns:
        suffix = " (nullable)" if c.nullable else ""
        lines.append(f"  {c.name} {c.dtype}{suffix}")
    return f"Table {table.name}:\n" + "\n".join(lines)


def _format_compact(table: Table) -> str:
    """紧凑格式：Table xxx: col1, col2, col3"""
    col_names = ", ".join(c.name for c in table.columns)
    return f"Table {table.name}: {col_names}"


def summarize_schema(tables: list[Table], max_tokens: int = 2000) -> str:
    """根据 token 限制裁剪 schema。

    策略：
    - 如果总 token 在限制内，返回完整格式
    - 否则按列数从多到少排序，前 N 张表保留完整格式，其余用紧凑格式
    """
    if not tables:
        return ""

    full_text = "\n\n".join(_format_full(t) for t in tables)
    if _estimate_tokens(full_text) <= max_tokens:
        return full_text

    sorted_tables = sorted(tables, key=lambda t: len(t.columns), reverse=True)

    result_parts = []
    token_budget = max_tokens

    for i, t in enumerate(sorted_tables):
        if i < len(sorted_tables) // 3:
            part = _format_full(t)
        else:
            part = _format_compact(t)

        part_tokens = _estimate_tokens(part)
        if token_budget - part_tokens < 0:
            compact = _format_compact(t)
            compact_tokens = _estimate_tokens(compact)
            if token_budget - compact_tokens >= 0:
                result_parts.append(compact)
                token_budget -= compact_tokens
            break

        result_parts.append(part)
        token_budget -= part_tokens

    return "\n\n".join(result_parts)
