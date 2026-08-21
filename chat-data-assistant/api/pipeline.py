"""查询管道：会话级 LLM 配置注入 + Text-to-SQL + 图表推荐。

不修改 ai/ 模块本身：ai.llm_client 在无 Streamlit 运行时的回退链终点是
config.Config 的类属性，这里在调用前后临时替换这些类属性（加锁防并发串扰）。
"""
import threading

from ai.text_to_sql import to_sql_with_correction
from config import config
from core.secrets import sanitize_error

_pipeline_lock = threading.Lock()

_LLM_FIELDS = ("LLM_PROVIDER", "LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY")


def _apply_session_llm(session_llm: dict):
    backup = {f: getattr(config, f) for f in _LLM_FIELDS}
    if session_llm.get("provider"):
        config.LLM_PROVIDER = session_llm["provider"]
    if session_llm.get("base_url"):
        config.LLM_BASE_URL = session_llm["base_url"]
    if session_llm.get("model"):
        config.LLM_MODEL = session_llm["model"]
    if session_llm.get("api_key"):
        config.LLM_API_KEY = session_llm["api_key"]
    return backup


def _restore_llm(backup: dict):
    for f, v in backup.items():
        setattr(config, f, v)


def run_query(schema_summary: str, history: list[dict], question: str,
              session_llm: dict) -> dict:
    """执行一次完整查询，返回 JSON 友好的结果字典。"""
    with _pipeline_lock:
        backup = _apply_session_llm(session_llm)
        try:
            sql, df, error = to_sql_with_correction(
                schema_summary=schema_summary,
                chat_history=history,
                user_query=question,
                execute_fn=execute_sql_safe,
            )
            recommendation = None
            if df is not None and not df.empty:
                from ai.chart_recommendation import recommend_chart
                try:
                    recommendation = recommend_chart(df, question, sql)
                except Exception:
                    recommendation = None
        finally:
            _restore_llm(backup)

    return {
        "sql": sql,
        "error": sanitize_error(error) if error else None,
        "recommendation": recommendation,
        **_dataframe_payload(df),
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
