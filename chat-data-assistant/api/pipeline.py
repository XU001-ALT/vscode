"""查询管道：会话级 LLM 配置 + 意图路由（chart/data/chat）。

LLM 配置通过 llm_cfg 参数显式传递（ai.llm_client 优先使用），
不再修改全局 config，因此多个请求可以并发执行、互不串扰，
无需全局锁串行化。

意图路由：
- chat: 寒暄/超范围问题，直接返回模型说明文字（answer），无 SQL 无图表
- data: 问数问题，返回表格；ENABLE_AI_SUMMARY 开启时额外生成 grounded 文字解读
- chart(缺省): 绘图问题，返回表格 + 图表推荐（原有行为）
"""
from ai.text_to_sql import to_sql_with_correction
from config import config
from core.secrets import sanitize_error

# 会话级 LLM 配置字段（与 sessions._new_session 的结构对应）
_LLM_CFG_FIELDS = ("provider", "base_url", "model", "api_key")


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
    elif outcome.error is None and outcome.df is not None and not outcome.df.empty:
        if outcome.intent == "data":
            if config.ENABLE_AI_SUMMARY:
                from ai.result_summary import summarize_result
                try:
                    answer = summarize_result(outcome.df, question, outcome.sql,
                                              lang=lang, llm_cfg=llm_cfg)
                except Exception:
                    answer = None
        else:
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
