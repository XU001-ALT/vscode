"""表描述（数据字典）加载：本地 JSON 配置，映射表名 → 中文说明。

描述有两个用途：
1. 侧边栏「数据使用说明」展示给用户看；
2. 注入 Text-to-SQL 的 schema，帮助 LLM 理解各表的业务含义。
"""
import json
from pathlib import Path

from schema.loader import Table

_DESC_PATH = Path(__file__).parent / "table_descriptions.json"


def load_descriptions() -> dict[str, str]:
    """读取表名 → 说明 的映射。文件缺失或格式错误时返回空字典。"""
    try:
        with open(_DESC_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def apply_descriptions(tables: list[Table]) -> list[Table]:
    """按表名把本地描述挂到 Table 对象上（未配置描述的表保持为空）。"""
    desc = load_descriptions()
    for t in tables:
        t.description = desc.get(t.name, "")
    return tables
