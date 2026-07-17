# schema 摘要工具：当 schema 很大时，生成摘要以节省 LLM token

def summarize_schema(schema_text, max_tokens=1000):
    # TODO: 实现摘要逻辑（可用简单的字段抽取或更复杂的 NLP）
    return schema_text[:2000]
