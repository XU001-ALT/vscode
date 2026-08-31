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
    "zh": "出于数据保护，我只能返回单值统计结论（如最高值、最低值、平均值、数量等单行特例值），无法返回明细数据、多行列表或图表。请换个问法，例如询问“最高温度是多少”。",
    "en": ("For data protection, I can only return single-value statistics (max, min, "
           "average, count — a single exceptional value) and cannot return detailed rows, "
           "lists, or charts. Please rephrase, e.g. 'what is the maximum temperature?'"),
}


def run_query(schema_summary: str, history: list[dict], question: str,
              session_llm: dict, lang: str = "zh") -> dict:
    """执行一次查询，返回 JSON 友好的结果字典。

    以保护数据为前提：不生成图表、不返回明细数据，也不暴露 SQL。
    所有查询只输出可安全展示的结论：
    - chat 意图：直接返回说明文字（answer）
    - 其余意图：强制收敛为单行统计特例值（MAX/MIN/AVG 等），以文字结论展示；
      若 SQL 不含聚合或返回多行（会被视为试图拉取明细数据），一律拒绝。
    """
    llm_cfg = {f: session_llm.get(f) or "" for f in _LLM_CFG_FIELDS}

    outcome = to_sql_with_correction(
        schema_summary=schema_summary,
        chat_history=history,
        user_query=question,
        execute_fn=execute_sql_safe,
        llm_cfg=llm_cfg,
        lang=lang,
    )

    # 只输出文字结论：绝不生成图表、绝不返回明细数据、绝不暴露 SQL。
    if outcome.intent == "chat":
        # 寒暄/超范围回应：说明文字
        return {
            "sql": None, "error": None, "recommendation": None,
            "answer": outcome.message, "intent": "chat",
            "corrections": None,
            "columns": [], "rows": [], "row_count": 0,
        }

    # 非 chat 意图：可安全展示的仅为「单行统计特例值」数据统计摘要，
    # SQL 不含聚合或返回多行（试图拉取明细）一律拒绝。
    refuse = _BULK_REFUSE.get(lang, _BULK_REFUSE["zh"])
    df = outcome.df
    if outcome.error is not None:
        return {
            "sql": None,
            "error": sanitize_error(outcome.error),
            "recommendation": None, "answer": None, "intent": "data",
            "corrections": None,
            "columns": [], "rows": [], "row_count": 0,
        }
    if df is None or not _AGG_RE.search(outcome.sql or "") or len(df) != 1:
        # 无法给出单值统计结论：拒绝（例如批量/明细类请求）
        return {
            "sql": None, "error": None, "recommendation": None,
            "answer": refuse, "intent": "data",
            "corrections": None,
            "columns": [], "rows": [], "row_count": 0,
        }

    # 允许返回：仅 1 行的聚合统计摘要（MAX/MIN/AVG 等特例值，作为文字结论展示）
    from api.serializers import df_to_json
    columns, rows = df_to_json(df)
    return {
        "sql": None, "error": None, "recommendation": None,
        "answer": None, "intent": "data",
        "corrections": None,
        "columns": columns, "rows": rows, "row_count": len(df),
    }


def execute_sql_safe(sql: str):
    from db.executor import execute_sql_safe as _exec
    return _exec(sql)
