# prompts 模块：构建 system prompt、user prompt 等

SYSTEM_PROMPT = "You are a PostgreSQL expert. Only generate SELECT queries based on provided schema."


def build_prompt(schema_summary, chat_history, user_query):
    return SYSTEM_PROMPT + "\nSchema:\n" + schema_summary + "\nUser: " + user_query
