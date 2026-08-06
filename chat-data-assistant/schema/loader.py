import json
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
    description: str = ""


# ------------------------------------------------------------
# 自定义文本格式：Table xxx:\n  列名 类型 (nullable)
# ------------------------------------------------------------

_TABLE_RE = re.compile(r"^Table\s+(\S+)\s*:", re.MULTILINE)
_COL_RE = re.compile(r"^\s+(\S+)\s+(\S+?)(?:\s+\(nullable\))?\s*$", re.MULTILINE)


def _parse_text_tables(text: str) -> list[Table]:
    """解析 'Table xxx:\n  col type' 格式的 schema 文本"""
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


# ------------------------------------------------------------
# Python ORM 解析（SQLAlchemy 声明式，仅用正则解析，不执行代码）
# ------------------------------------------------------------

_ORM_TABLENAME_RE = re.compile(r"__tablename__\s*=\s*['\"]([^'\"]+)['\"]")
_ORM_CLASSIC_COL_RE = re.compile(r"(\w+)\s*=\s*Column\(")
_ORM_V2_COL_RE = re.compile(r"(\w+)\s*:\s*Mapped\s*\[([^\]]*)\]\s*=\s*mapped_column\(")
_ORM_FIRST_QUOTED = re.compile(r"^['\"]([^'\"]+)['\"]\s*,")
_ORM_TYPE_IDENT = re.compile(r"\s*([A-Za-z_][\w.]*)\s*(?:\(|,|$)")


def _scan_balanced_call(text: str, call_start: int, open_pos: int) -> str:
    """从 open_pos（紧跟函数名后的 '('）开始扫描，返回参数文本（含括号内内容）。"""
    depth = 1
    i = open_pos + 1
    while i < len(text) and depth:
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
        i += 1
    if depth == 0:
        return text[open_pos + 1: i - 1]
    return text[open_pos + 1: i]


def _parse_orm_column(attr: str, args: str, type_hint: str = "") -> Column | None:
    """解析单个 Column/mapped_column 调用的参数，返回 Column。

    - 第一个参数若是字符串，则作为列名（覆盖属性名）
    - 类型取第一个标识符（String(100) -> String，sqlalchemy.Integer -> Integer）
    - 没有显式类型时回退到 Mapped[type] 的类型提示
    """
    args = args.strip()
    if not args:
        return None

    name = attr
    rest = args
    m = _ORM_FIRST_QUOTED.match(args)
    if m:
        name = m.group(1)
        rest = args[m.end():]

    dtype = ""
    m = _ORM_TYPE_IDENT.match(rest)
    if m:
        dtype = m.group(1).split(".")[-1]
    if not dtype:
        dtype = type_hint.split(".")[-1].strip()

    nullable = re.search(r"nullable\s*=\s*True", args) is not None

    if not name or not dtype:
        return None
    return Column(name=name, dtype=dtype, nullable=nullable)


def _parse_python_orm(text: str) -> list[Table]:
    """解析 SQLAlchemy 声明式 ORM 源码（classic Column 与 2.0 Mapped 风格）。

    只做正则/文本扫描，绝不 exec 上传的代码，避免任意代码执行风险。
    """
    tablename_hits = [(m.group(1), m.start()) for m in _ORM_TABLENAME_RE.finditer(text)]

    col_hits = []  # (attr, args, dtype_hint, pos)
    for m in _ORM_CLASSIC_COL_RE.finditer(text):
        open_pos = text.find("(", m.end() - 1)
        args = _scan_balanced_call(text, m.start(), open_pos)
        col_hits.append((m.group(1), args, "", m.start()))
    for m in _ORM_V2_COL_RE.finditer(text):
        open_pos = text.find("(", m.end() - 1)
        args = _scan_balanced_call(text, m.start(), open_pos)
        col_hits.append((m.group(1), args, m.group(2), m.start()))

    if not tablename_hits or not col_hits:
        return []

    tables: dict[str, list[Column]] = {}
    for attr, args, type_hint, pos in sorted(col_hits, key=lambda x: x[3]):
        table_name = None
        for tn, tp in tablename_hits:
            if tp < pos:
                table_name = tn
            else:
                break
        if table_name is None:
            continue
        col = _parse_orm_column(attr, args, type_hint)
        if col:
            tables.setdefault(table_name, []).append(col)

    return [Table(name=n, columns=cols) for n, cols in tables.items()]


# ------------------------------------------------------------
# JSON 解析：{表名: [列对象,...]} 或 [{table/name: 表名, columns/fields: [...]}]
# ------------------------------------------------------------

def _column_from_json_dict(c: dict) -> Column:
    name = c.get("name") or c.get("column") or c.get("field") or ""
    dtype = c.get("type") or c.get("dtype") or c.get("data_type") or ""
    nullable = c.get("nullable")
    if nullable is None:
        nullable = str(c.get("is_nullable", "")).upper() in ("YES", "TRUE")
    return Column(name=str(name), dtype=str(dtype), nullable=bool(nullable))


def _parse_json(text: str) -> list[Table]:
    try:
        data = json.loads(text)
    except Exception:
        return []

    tables: list[Table] = []

    def _columns_from_list(cols) -> list[Column]:
        result = []
        for c in cols:
            if isinstance(c, dict):
                result.append(_column_from_json_dict(c))
        return result

    if isinstance(data, dict):
        for name, cols in data.items():
            if isinstance(cols, list):
                tables.append(Table(name=str(name), columns=_columns_from_list(cols)))
            elif isinstance(cols, dict):
                inner = cols.get("columns") or cols.get("fields") or []
                tables.append(Table(name=str(name), columns=_columns_from_list(inner)))
    elif isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            name = item.get("table") or item.get("table_name") or item.get("name")
            if name is None:
                continue
            cols = item.get("columns") or item.get("fields") or item.get("properties") or []
            tables.append(Table(name=str(name), columns=_columns_from_list(cols)))

    return [t for t in tables if t.name]


# ------------------------------------------------------------
# 统一入口：自动识别文本 / JSON / Python ORM
# ------------------------------------------------------------

def load_from_text(text: str) -> list[Table]:
    """解析 schema 文本，自动识别三种格式：
    1. 自定义文本（Table xxx:\n  col type）
    2. JSON（对象/数组两种结构）
    3. Python SQLAlchemy 声明式 ORM 源码
    """
    text = text.strip()
    if not text:
        return []

    if text[0] in "[{":
        tables = _parse_json(text)
        if tables:
            return tables

    if "__tablename__" in text or re.search(r"=\s*Column\(", text) or "mapped_column(" in text:
        tables = _parse_python_orm(text)
        if tables:
            return tables

    return _parse_text_tables(text)


def schema_to_text(tables: list[Table]) -> str:
    """将结构化 Table 列表转回文本格式"""
    lines = []
    for t in tables:
        header = f"Table {t.name}:"
        if t.description:
            header += f" {t.description}"
        col_lines = []
        for c in t.columns:
            suffix = " (nullable)" if c.nullable else ""
            col_lines.append(f"  {c.name} {c.dtype}{suffix}")
        lines.append(header + "\n" + "\n".join(col_lines))
    return "\n\n".join(lines)
