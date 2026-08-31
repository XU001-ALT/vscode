"""
图表自动推荐：根据用户问题 + 执行结果，让 LLM 推断图表类型和坐标轴。

用户用自然语言描述需求（如"绘制各种材料在数据库中总词条的占比"），
SQL 执行得到结果集后，这里让 LLM 给出 {chart_type, x_col, y_col, reason}。

推荐会做两层校验：
1. 类型/列名/唯一值数是否合法（dtype 级别，防止渲染报错）
2. 校验失败或 LLM 调用失败时，回退到启发式兜底推荐，保证总能出图
"""
import json

import pandas as pd

from .llm_client import call_llm_raw
from .prompts import build_chart_recommendation_prompt, PIE_MAX_CATEGORIES

VALID_CHART_TYPES = {
    "line", "bar", "scatter", "pie", "area", "histogram",
    "bubble", "scatter3d", "heatmap", "parallel", "box", "radar",
}

# 无需显式 y_col 的图表（渲染时由前端自动取全部数值列 / 指定数值列）：
# histogram 由 x_col 决定，heatmap/parallel/radar 由数值列集合自动构建
AUTO_COLUMN_CHARTS = {"histogram", "heatmap", "parallel", "radar"}

# 需要三个数值轴（x/y/z）的图表；z_col 缺失时由前端回退到第三个数值列
THREE_D_CHARTS = {"scatter3d"}


def _extract_json(text: str) -> dict | None:
    """从 LLM 回复中解析 JSON（兼容 ```json 代码块与前后夹带文字）。"""
    t = text.strip()
    if "```" in t:
        for part in t.split("```"):
            p = part.strip().lstrip("json").strip()
            if p.startswith("{") and p.endswith("}"):
                t = p
                break
    try:
        return json.loads(t)
    except Exception:
        start, end = t.find("{"), t.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            return json.loads(t[start:end + 1])
        except Exception:
            return None


def _is_numeric_col(df: pd.DataFrame, col: str) -> bool:
    return pd.api.types.is_numeric_dtype(df[col])


def _is_scalar_col(df: pd.DataFrame, col: str) -> bool:
    """列值是否全部为标量（不含 jsonb/dict/list，避免渲染成字符串）。"""
    try:
        return not bool(df[col].map(lambda v: isinstance(v, (dict, list))).any())
    except Exception:
        return True


def _safe_nunique(df: pd.DataFrame, col: str) -> int:
    """统计列的唯一值数，兼容 jsonb/dict/list 等不可哈希值（转字符串后统计）。"""
    try:
        return int(df[col].nunique(dropna=True))
    except TypeError:
        return int(df[col].astype(str).nunique(dropna=True))


def _column_info(df: pd.DataFrame) -> str:
    """生成列信息摘要：`列名 (数值/文本, N 个唯一值)`，帮助 LLM 判断坐标轴是否合理。"""
    parts = []
    for col in df.columns:
        kind = "数值" if _is_numeric_col(df, col) else "文本"
        nunique = _safe_nunique(df, col)
        parts.append(f"- {col} ({kind}, {nunique} 个唯一值)")
    return "\n".join(parts)


def _normalize_rec(data: dict) -> dict | None:
    """从 LLM 返回的 dict 中提取并规整推荐字段。"""
    if not isinstance(data, dict):
        return None
    chart_type = str(data.get("chart_type", "")).strip().lower()
    x_col = str(data.get("x_col", "")).strip()
    y_col = str(data.get("y_col", "")).strip()
    z_col = str(data.get("z_col", "")).strip()
    reason = str(data.get("reason", "")).strip()
    if not chart_type or not x_col:
        return None
    if not y_col and chart_type not in AUTO_COLUMN_CHARTS:
        return None
    rec = {"chart_type": chart_type, "x_col": x_col, "y_col": y_col, "reason": reason}
    if z_col:
        rec["z_col"] = z_col
    return rec


def _valid_rec(df: pd.DataFrame, rec: dict) -> bool:
    """校验 LLM 推荐是否可在当前结果集上安全渲染（dtype 级别）。"""
    chart_type = rec["chart_type"]
    x = rec.get("x_col", "") or ""
    y = rec.get("y_col", "") or ""
    z = rec.get("z_col", "") or ""
    numeric = [c for c in df.columns if _is_numeric_col(df, c)]

    if chart_type not in VALID_CHART_TYPES:
        return False

    # 直方图：单个数值列的分布，x_col 决定，y_col 不使用
    if chart_type == "histogram":
        return x in df.columns and _is_scalar_col(df, x) and _is_numeric_col(df, x)
    # 多指标自动类：heatmap/parallel 自动使用全部数值列，radar 至少一个指标
    if chart_type in ("heatmap", "parallel"):
        return len(numeric) >= 2
    if chart_type == "radar":
        return len(numeric) >= 1

    if x not in df.columns:
        return False

    if chart_type in THREE_D_CHARTS:
        # 三维散点：X/Y 必须是数值列，Z 缺失时由前端回退到第三个数值列
        if y not in df.columns or x not in numeric or y not in numeric:
            return False
        if z and (z not in df.columns or z not in numeric):
            return False
        return len(numeric) >= 3

    if x == y:
        return False
    if y not in df.columns:
        return False
    # 坐标轴不能用 jsonb/dict/list 列（渲染成字符串无意义）
    if not _is_scalar_col(df, x) or not _is_scalar_col(df, y):
        return False

    if chart_type == "pie":
        # 饼图：数值列作为占比，且分类数不能过多
        if not _is_numeric_col(df, y):
            return False
        if _safe_nunique(df, x) > PIE_MAX_CATEGORIES:
            return False
    elif chart_type == "bubble":
        # 气泡散点：X/Y 都应为数值，气泡大小由前端另选
        if not _is_numeric_col(df, x) or not _is_numeric_col(df, y):
            return False
    elif chart_type == "box":
        # 箱线图：Y 必须是数值列（X 为分类或数值均可）
        if not _is_numeric_col(df, y):
            return False
    else:
        # 折线/柱状/散点/面积：Y 轴必须是数值列，否则 plotly 无法渲染
        if not _is_numeric_col(df, y):
            return False
    return True


def _fallback_recommendation(df: pd.DataFrame) -> dict | None:
    """启发式兜底推荐：LLM 失败或推荐无效时，生成一个能安全渲染的默认图。"""
    if df is None or df.empty:
        return None

    numeric = [c for c in df.columns if _is_numeric_col(df, c)]
    non_numeric = [c for c in df.columns
                   if not _is_numeric_col(df, c) and _is_scalar_col(df, c)]

    if not numeric:
        return None

    if non_numeric:
        x = non_numeric[0]
        y = numeric[0]
        if _safe_nunique(df, x) <= PIE_MAX_CATEGORIES and len(numeric) == 1:
            return {"chart_type": "pie", "x_col": x, "y_col": y,
                    "reason": "自动选择：单一分类列 + 单一数值列，用饼图展示占比。"}
        return {"chart_type": "bar", "x_col": x, "y_col": y,
                "reason": "自动选择：分类列对比数值，用柱状图。"}

    if len(numeric) >= 2:
        return {"chart_type": "scatter", "x_col": numeric[0], "y_col": numeric[1],
                "reason": "自动选择：双数值列，用散点图查看相关性。"}

    return {"chart_type": "histogram", "x_col": numeric[0], "y_col": "",
            "reason": "自动选择：单一数值列，用直方图查看分布。"}


def recommend_chart(df, user_query: str, sql: str,
                    llm_cfg: dict | None = None) -> dict | None:
    """推荐图表配置。

    Args:
        df: SQL 执行结果 DataFrame
        user_query: 用户的原始自然语言问题
        sql: 已执行的 SQL
        llm_cfg: 会话级 LLM 配置（见 call_llm_raw）

    Returns:
        {"chart_type": "line|bar|scatter|pie", "x_col": str, "y_col": str, "reason": str}
        LLM 失败且无兜底方案时才返回 None
    """
    if df is None or df.empty:
        return None

    prompt = build_chart_recommendation_prompt(
        user_query, sql, list(df.columns), len(df), _column_info(df)
    )
    try:
        raw = call_llm_raw(prompt, max_tokens=1024, temperature=0.0, llm_cfg=llm_cfg)
    except Exception:
        return _fallback_recommendation(df)

    rec = _normalize_rec(_extract_json(raw))
    if rec and _valid_rec(df, rec):
        return rec
    return _fallback_recommendation(df)
