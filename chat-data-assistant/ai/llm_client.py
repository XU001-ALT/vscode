# 简单 LLM 客户端封装（占位）
import os

API_KEY = os.getenv('OPENAI_API_KEY', '')


def call_llm(prompt, max_tokens=512):
    # TODO: 集成 OpenAI / 其他提供方的 API
    return "--LLM 输出占位--"
