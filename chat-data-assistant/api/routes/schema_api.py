"""Schema 管理接口：从数据库拉取 / 上传解析。"""
from fastapi import APIRouter
from pydantic import BaseModel

from db.executor import fetch_full_schema
from schema.loader import load_from_text
from schema.validator import validate_schema
from schema.summarizer import summarize_schema

router = APIRouter(prefix="/api")


class SchemaUpload(BaseModel):
    content: str


def _process(raw_text: str) -> dict:
    tables = load_from_text(raw_text)
    ok, errors = validate_schema(tables)
    if not ok:
        return {"ok": False, "error": "; ".join(errors), "tables": []}
    processed = summarize_schema(tables)
    names = [t.name for t in tables]
    from api.state import set_schema
    set_schema(processed, names)
    return {"ok": True, "error": "", "tables": names}


@router.post("/schema/fetch")
def fetch_schema():
    """从数据库拉取全部表结构并处理（等价于原侧边栏「拉取 Schema」按钮）。"""
    try:
        raw = fetch_full_schema()
    except Exception as e:
        return {"ok": False, "error": str(e), "tables": []}
    return _process(raw)


@router.post("/schema/upload")
def upload_schema(body: SchemaUpload):
    """上传 ORM / JSON / 文本格式 schema 并处理。"""
    try:
        return _process(body.content)
    except Exception as e:
        return {"ok": False, "error": str(e), "tables": []}


@router.get("/schema/descriptions")
def get_descriptions():
    """表数据字典（表名 → 中文说明），供「数据使用声明」展示。"""
    from schema.descriptions import load_descriptions
    return load_descriptions()
