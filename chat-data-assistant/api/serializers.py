"""DataFrame / 值的 JSON 安全序列化。"""
import datetime
import decimal
import math

import numpy as np
import pandas as pd


def _cell(v) -> object:
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return v
    if isinstance(v, (pd.Timestamp, datetime.datetime)):
        return None if pd.isna(v) else v.isoformat(sep=" ")
    if isinstance(v, datetime.date):
        return None if pd.isna(v) else v.isoformat()
    if isinstance(v, (datetime.timedelta, pd.Timedelta)):
        return str(v)
    if isinstance(v, decimal.Decimal):
        return None if pd.isna(v) else float(v)
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    if isinstance(v, str):
        return v
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    if isinstance(v, (int, bool)):
        return v
    return str(v)


def df_to_json(df: pd.DataFrame) -> tuple[list[str], list[list]]:
    """返回 (columns, rows)，rows 为二维数组，前端直接渲染表格。"""
    columns = [str(c) for c in df.columns]
    rows = [[_cell(v) for v in record] for record in df.itertuples(index=False, name=None)]
    return columns, rows
