"""
图表自动推荐：根据用户问题 + 执行结果，让 LLM 推断图表类型和坐标轴。

用户用自然语言描述需求（如"绘制各种材料在数据库中总词条的占比"），
SQL 执行得到结果集后，这里让 LLM 给出 {chart_type, x_col, y_col, reason}。
"""
import json

from .llm_client import call_llm_raw
from .prompts import build_chart_recommendation_prompt

VALID_CHART_TYPES = {"line", "bar", "scatter", "pie"}


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


def recommend_chart(df, user_query: str, sql: str) -> dict | None:
    """推荐图表配置。

    Args:
        df: SQL 执行结果 DataFrame
        user_query: 用户的原始自然语言问题
        sql: 已执行的 SQL

    Returns:
        {"chart_type": "line|bar|scatter|pie", "x_col": str, "y_col": str, "reason": str}
        解析/校验失败时返回 None
    """
    if df is None or df.empty:
        return None
    columns = list(df.columns)
    prompt = build_chart_recommendation_prompt(user_query, sql, columns, len(df))
    try:
        raw = call_llm_raw(prompt, max_tokens=1024, temperature=0.0)
    except Exception:
        return None

    data = _extract_json(raw)
    if not data:
        return None

    chart_type = str(data.get("chart_type", "")).strip().lower()
    x_col = str(data.get("x_col", "")).strip()
    y_col = str(data.get("y_col", "")).strip()
    reason = str(data.get("reason", "")).strip()

    if chart_type not in VALID_CHART_TYPES:
        return None
    if not x_col or not y_col:
        return None
    if x_col not in columns or y_col not in columns:
        return None
    if x_col == y_col:
        return None

    return {"chart_type": chart_type, "x_col": x_col, "y_col": y_col, "reason": reason}
