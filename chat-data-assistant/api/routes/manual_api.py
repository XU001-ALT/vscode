"""手动可视化接口（无 LLM、无 API Key，纯只读取数）。

供「手动绘图面板」使用：前端选表 → 绑定轴 → 筛选，后端只做只读查询返回数据，
由 ChartView 前端渲染 8 种固定图表。
"""
from fastapi import APIRouter
from pydantic import BaseModel

from db.connection import get_engine
from db.executor import execute_sql_safe, is_business_table

router = APIRouter(prefix="/api/manual")


# 可作为类别（分箱）轴的 PG 类型子串
_CATEGORY_TYPES = ("character", "char ", "text", "varchar", "timestamp")


@router.get("/tables")
def manual_tables():
    """所有业务表及其列信息（列名 / 类型 / 是否数值近似）。"""
    engine = get_engine()
    try:
        with engine.connect() as conn:
            import sqlalchemy as sa

            tables_res = conn.execute(sa.text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            ))
            tables = []
            for (t,) in tables_res:
                if not is_business_table(t):
                    continue
                cols_res = conn.execute(sa.text(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_name = :t AND table_schema = 'public' "
                    "ORDER BY ordinal_position"
                ), {"t": t})
                cols = [{
                    "name": c,
                    "data_type": dt,
                    "numeric": _looks_numeric(dt),
                    "categorical": _looks_categorical(dt),
                } for c, dt in cols_res]
                tables.append({"name": t, "columns": cols})
            return {"ok": True, "tables": tables}
    except Exception as e:
        from core.secrets import sanitize_error
        return {"ok": False, "error": sanitize_error(str(e)), "tables": []}


def _looks_numeric(dt: str) -> bool:
    d = (dt or "").lower()
    for k in ("int", "real", "float", "numeric", "double", "decimal"):
        if k in d:
            return True
    return False


def _looks_categorical(dt: str) -> bool:
    d = (dt or "").lower()
    return any(k in d for k in ("char", "text", "varchar", "timestamp"))


class RowsRequest(BaseModel):
    table: str
    limit: int | None = 1000


@router.post("/rows")
def manual_rows(req: RowsRequest):
    """返回指定表的前 N 行（只读，受表名白名单与行数限制保护）。"""
    table = (req.table or "").strip()
    if not table:
        return {"ok": False, "error": "未指定数据表", "columns": [], "rows": [], "row_count": 0}
    if not is_business_table(table):
        return {"ok": False, "error": "不允许访问该系统表", "columns": [], "rows": [], "row_count": 0}
    limit = min(req.limit or 1000, 2000)
    sql = f'SELECT * FROM "{table}" LIMIT {int(limit)}'
    df, err = execute_sql_safe(sql, max_rows=limit)
    if err:
        return {"ok": False, "error": err, "columns": [], "rows": [], "row_count": 0}
    if df is None:
        return {"ok": False, "error": "查询未返回数据", "columns": [], "rows": [], "row_count": 0}
    from api.serializers import df_to_json
    columns, rows = df_to_json(df)
    return {"ok": True, "error": None, "columns": columns, "rows": rows, "row_count": len(df)}
