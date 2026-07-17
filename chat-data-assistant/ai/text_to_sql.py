from .prompts import build_prompt
from .llm_client import call_llm


def to_sql(schema_summary, chat_history, user_query):
    prompt = build_prompt(schema_summary, chat_history, user_query)
    sql = call_llm(prompt)
    # TODO: 调用 sql_guard 校验
    return sql
