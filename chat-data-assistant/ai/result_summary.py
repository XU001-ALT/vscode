"""问数模式结果解读：把 SQL 查询结果转成简短的文字结论。

数据最小化设计：
- 只发送前 N 行样本 + 总行数给 LLM（提示词引导问数类 SQL 自带聚合，
  因此正常情况下样本即全量或接近全量）
- 长文本单元格截断，总字符预算封顶
- 严格 grounded 提示词：只允许引用给定数字，禁止编造/估算
"""
import json

import pandas as pd

from .llm_client import call_llm_raw
from .prompts import build_result_summary_prompt

# 发送给 LLM 的最大行数与单元格截断长度
MAX_PREVIEW_ROWS = 30
MAX_CELL_CHARS = 80
# 行样本总字符预算（超出则减少行数）
MAX_PREVIEW_CHARS = 6000


def _cell_str(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "null"
    if isinstance(v, float):
        # repr 保留精度，避免浮点噪声；整数化的值去掉 .0
        return str(int(v)) if v.is_integer() else repr(v)
    s = str(v)
    if len(s) > MAX_CELL_CHARS:
        s = s[:MAX_CELL_CHARS] + "…"
    return s.replace("\n", " ")


def _preview_lines(df: pd.DataFrame) -> tuple[str, int]:
    """生成行样本文本，返回 (文本, 实际发送的行数)。超预算时逐步减行。"""
    n = min(MAX_PREVIEW_ROWS, len(df))
    while n > 0:
        records = [
            {col: _cell_str(v) for col, v in zip(df.columns, row)}
            for row in df.head(n).itertuples(index=False, name=None)
        ]
        text = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
        if len(text) <= MAX_PREVIEW_CHARS:
            return text, n
        n = max(1, int(n * 0.7))
    return "", 0


def summarize_result(df, user_query: str, sql: str,
                     lang: str = "zh", llm_cfg: dict | None = None) -> str | None:
    """生成 grounded 文字结论。LLM 失败时返回 None（前端退化为仅表格展示）。"""
    if df is None or df.empty:
        return None

    preview, sent_rows = _preview_lines(df)
    row_count = len(df)
    note = "" if sent_rows >= row_count else f"（样本仅含前 {sent_rows} 行）"
    prompt = build_result_summary_prompt(
        user_query=user_query,
        sql=sql,
        columns=[str(c) for c in df.columns],
        rows_preview_lines=preview + note,
        row_count=row_count,
        lang=lang,
    )
    try:
        reply = call_llm_raw(prompt, max_tokens=1024, temperature=0.2, llm_cfg=llm_cfg)
    except Exception:
        return None
    reply = (reply or "").strip()
    # 剔除模型偶尔附带的代码围栏
    if "```" in reply:
        parts = [p.strip() for p in reply.split("```")]
        reply = max(parts, key=len).strip()
    return reply or None
