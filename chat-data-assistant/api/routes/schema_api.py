"""Schema 数据字典接口。"""
from fastapi import APIRouter

router = APIRouter(prefix="/api")


@router.get("/schema/descriptions")
def get_descriptions():
    """表数据字典（表名 → 中文说明），供「数据使用声明」展示。"""
    from schema.descriptions import load_descriptions
    return load_descriptions()
