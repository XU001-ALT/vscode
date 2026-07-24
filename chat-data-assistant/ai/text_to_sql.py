from .llm_client import call_llm
from .prompts import build_prompt
from .sql_guard import validate_sql


def _extract_sql_text(text: str) -> str:
    return text.strip()


def to_sql(schema_summary: str, chat_history: list[dict], user_query: str) -> str:
    prompt = build_prompt(schema_summary, chat_history, user_query)
    raw_sql = call_llm(prompt)
    sql = _extract_sql_text(raw_sql)
    valid, error = validate_sql(sql)
    if not valid:
        raise ValueError(f"LLM 生成的 SQL 校验失败：{error}\n{sql}")
    return sql
