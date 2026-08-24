"""查询管道：会话级 LLM 配置 + 意图路由（chart/data/chat）。

LLM 配置通过 llm_cfg 参数显式传递（ai.llm_client 优先使用），
不再修改全局 config，因此多个请求可以并发执行、互不串扰，
无需全局锁串行化。

意图路由：
- chat: 寒暄/超范围问题或试图批量获取数据的请求，直接返回说明文字（answer），无 SQL 无图表
- data: 问数问题，仅允许单行聚合统计（最大值、最小值、平均值等特例值），结果由前端以回答框展示
- chart(缺省): 绘图问题，返回表格 + 图表推荐（原有行为）
"""
import re

from ai.text_to_sql import to_sql_with_correction
from core.secrets import sanitize_error

# 会话级 LLM 配置字段（与 sessions._new_session 的结构对应）
_LLM_CFG_FIELDS = ("provider", "base_url", "model", "api_key")

# data 意图兜底拦截：SQL 中不含任何聚合函数 => 视为试图批量拉取明细数据。
# 提示词已要求 data SQL 必带聚合，这里是模型不守规矩时的服务端最后防线。
_AGG_RE = re.compile(
    r"\b(MAX|MIN|AVG|COUNT|SUM|STDDEV(?:_POP|_SAMP)?|VARIANCE|VAR_POP|VAR_SAMP"
    r"|MEDIAN|PERCENTILE_CONT|PERCENTILE_DISC|MODE)\s*\(",
    re.IGNORECASE,
)

_BULK_REFUSE = {
    "zh": "抱歉，无法进行批量操作。问数模式仅支持查询最大值、最小值、平均值等单行统计特例值，请换个问法试试。",
    "en": ("Sorry, bulk operations are not supported. Query mode only returns "
           "single-row statistics such as max, min, and average — please rephrase your question."),
}


def run_query(schema_summary: str, history: list[dict], question: str,
              session_llm: dict, lang: str = "zh") -> dict:
    """执行一次完整查询，返回 JSON 友好的结果字典。"""
    llm_cfg = {f: session_llm.get(f) or "" for f in _LLM_CFG_FIELDS}

    outcome = to_sql_with_correction(
        schema_summary=schema_summary,
        chat_history=history,
        user_query=question,
        execute_fn=execute_sql_safe,
        llm_cfg=llm_cfg,
        lang=lang,
    )

    answer = None
    recommendation = None
    if outcome.intent == "chat":
        answer = outcome.message
    elif outcome.intent == "data" and outcome.error is None and outcome.df is not None:
        # 兜底拒绝两种情况（不向客户端返回任何明细行）：
        # 1. SQL 完全不含聚合函数 —— 明细拉取
        # 2. 结果多于一行 —— GROUP BY 等多行分组统计同样视为批量操作
        if not _AGG_RE.search(outcome.sql or "") or len(outcome.df) > 1:
            answer = _BULK_REFUSE.get(lang, _BULK_REFUSE["zh"])
            outcome = outcome._replace(df=None)
    elif outcome.error is None and outcome.df is not None and not outcome.df.empty:
        from ai.chart_recommendation import recommend_chart
        try:
            recommendation = recommend_chart(outcome.df, question, outcome.sql,
                                             llm_cfg=llm_cfg)
        except Exception:
            recommendation = None

    return {
        "sql": outcome.sql,
        "error": sanitize_error(outcome.error) if outcome.error else None,
        "recommendation": recommendation,
        "answer": answer,
        "intent": outcome.intent,
        **_dataframe_payload(outcome.df),
    }


def execute_sql_safe(sql: str):
    from db.executor import execute_sql_safe as _exec
    return _exec(sql)


def _dataframe_payload(df) -> dict:
    if df is None:
        return {"columns": [], "rows": [], "row_count": 0}
    from api.serializers import df_to_json
    columns, rows = df_to_json(df)
    return {"columns": columns, "rows": rows, "row_count": len(df)}
