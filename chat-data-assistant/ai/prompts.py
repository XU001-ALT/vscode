# prompts 模块：构建 system prompt、user prompt 等

SYSTEM_PROMPT = "You are a PostgreSQL expert. Only generate SELECT queries based on provided schema."


def build_prompt(schema_summary, chat_history, user_query):
    parts = [SYSTEM_PROMPT, "\nSchema:\n" + schema_summary]

    if chat_history:
        history_lines = []
        for msg in chat_history[-14:]:
            role = "User" if msg.get("role") == "user" else "Assistant"
            history_lines.append(f"{role}: {msg.get('content', '')}")
        parts.append("\n对话历史:\n" + "\n".join(history_lines))

    parts.append("\nUser: " + user_query)
    return "\n".join(parts)
