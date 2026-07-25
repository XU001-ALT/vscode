import re
from dataclasses import dataclass, field


@dataclass
class Column:
    name: str
    dtype: str
    nullable: bool = False


@dataclass
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)


_TABLE_RE = re.compile(r"^Table\s+(\S+)\s*:", re.MULTILINE)
_COL_RE = re.compile(r"^\s+(\S+)\s+(\S+?)(?:\s+\(nullable\))?\s*$", re.MULTILINE)


def load_from_text(text: str) -> list[Table]:
    """解析 'Table xxx:\n  col type' 格式的 schema 文本，返回 Table 列表"""
    tables = []
    parts = _TABLE_RE.split(text)

    if len(parts) < 2:
        return tables

    for i in range(1, len(parts), 2):
        table_name = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""

        columns = []
        for m in _COL_RE.finditer(body):
            col_name = m.group(1)
            col_dtype = m.group(2)
            nullable = "(nullable)" in m.group(0)
            columns.append(Column(name=col_name, dtype=col_dtype, nullable=nullable))

        tables.append(Table(name=table_name, columns=columns))

    return tables


def schema_to_text(tables: list[Table]) -> str:
    """将结构化 Table 列表转回文本格式"""
    lines = []
    for t in tables:
        col_lines = []
        for c in t.columns:
            suffix = " (nullable)" if c.nullable else ""
            col_lines.append(f"  {c.name} {c.dtype}{suffix}")
        lines.append(f"Table {t.name}:\n" + "\n".join(col_lines))
    return "\n\n".join(lines)
