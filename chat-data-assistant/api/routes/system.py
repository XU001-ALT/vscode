"""系统状态接口。"""
from fastapi import APIRouter

from core import bootstrap

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/bootstrap")
def bootstrap_state():
    """前端首屏轮询：数据库连接状态 + 当前 schema 概要。"""
    from api.state import get_schema, set_schema
    state = bootstrap.get_state()
    schema, tables = get_schema()

    # api/state 为空时，用后台线程自动拉取的结果回填（保持单一数据源语义）
    if not schema and state["done"] and state["schema"]:
        schema, tables = state["schema"], state["tables"]
        set_schema(schema, tables)

    db_info = None
    if state["connected"]:
        try:
            from db.connection import db_manager
            db_info = db_manager.get_info()
        except Exception:
            db_info = None
    return {
        "db": {**state, "info": db_info},
        "schema": {"text": schema, "tables": tables},
    }
