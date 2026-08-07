from schema.loader import Table, infer_relationships, format_relationships_text
from schema.descriptions import apply_descriptions


def _estimate_tokens(text: str) -> int:
    """粗略估算 token 数（英文约 4 字符/token，中文约 1.5 字符/token）"""
    return max(1, len(text) // 4)


def _format_full(table: Table, highlight_fk: set[str] | None = None) -> str:
    """完整格式：Table xxx: 描述\n  col type [FK→xxx]"""
    header = f"Table {table.name}:"
    if table.description:
        header += f" {table.description}"
    lines = []
    fk_set = highlight_fk or set()
    for c in table.columns:
        suffix = ""
        if c.nullable:
            suffix = " (nullable)"
        if c.name.lower() in fk_set:
            suffix += " ← FK"
        lines.append(f"  {c.name} {c.dtype}{suffix}")
    return header + "\n" + "\n".join(lines)


def _format_compact(table: Table) -> str:
    """紧凑格式：Table xxx (描述): col1, col2, col3"""
    col_names = ", ".join(c.name for c in table.columns)
    label = f"Table {table.name}"
    if table.description:
        label += f" ({table.description})"
    return f"{label}: {col_names}"


def _collect_fk_columns(relationships: list[dict]) -> dict[str, set[str]]:
    """收集每张表的哪些列是外键（用于 schema 中标注 ← FK）。"""
    result: dict[str, set[str]] = {}
    for r in relationships:
        tbl = r["from_table"]
        col = r["from_col"].lower()
        result.setdefault(tbl, set()).add(col)
    return result


def summarize_schema(tables: list[Table], max_tokens: int = 2000) -> str:
    """根据 token 限制裁剪 schema，并注入本地表描述（数据字典）和表关联关系。

    策略：
    - 如果总 token 在限制内，返回：关系提示 + 完整 schema
    - 否则优先保留列多的大表，小表用紧凑格式
    - 外键列标注 ← FK，帮助 LLM 识别 JOIN 条件
    """
    if not tables:
        return ""

    apply_descriptions(tables)

    # 推断表间关系
    relationships = infer_relationships(tables)
    fk_map = _collect_fk_columns(relationships)
    rel_text = format_relationships_text(relationships)

    parts: list[str] = []

    # 关系提示放在最前面，让 LLM 优先看到
    if rel_text:
        parts.append(rel_text)

    # Schema 正文
    full_text = "\n\n".join(_format_full(t, fk_map.get(t.name)) for t in tables)
    if _estimate_tokens(full_text) <= max_tokens:
        parts.append(full_text)
    else:
        sorted_tables = sorted(tables, key=lambda t: len(t.columns), reverse=True)
        schema_parts = []
        token_budget = max_tokens

        for i, t in enumerate(sorted_tables):
            if i < len(sorted_tables) // 3:
                part = _format_full(t, fk_map.get(t.name))
            else:
                part = _format_compact(t)

            part_tokens = _estimate_tokens(part)
            if token_budget - part_tokens < 0:
                compact = _format_compact(t)
                compact_tokens = _estimate_tokens(compact)
                if token_budget - compact_tokens >= 0:
                    schema_parts.append(compact)
                    token_budget -= compact_tokens
                break

            schema_parts.append(part)
            token_budget -= part_tokens

        parts.append("\n\n".join(schema_parts))

    return "\n\n".join(parts)
