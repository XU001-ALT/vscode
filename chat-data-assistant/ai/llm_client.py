"""LLM 调用封装，支持 OpenAI、DeepSeek 和本地开发模式。"""
import re
from typing import Any

import httpx
from config import config

_SQL_START_RE = re.compile(r"^\s*(select|with|explain|show|describe|desc)\b", re.IGNORECASE | re.MULTILINE)


def _normalize_response_text(text: str) -> str:
    text = text.strip()

    if "```" in text:
        pieces = text.split("```")
        if len(pieces) >= 3:
            inner = pieces[1].strip()
        else:
            inner = pieces[-1].strip()
    else:
        inner = text

    lines = inner.split("\n", 1)
    if lines:
        tag = lines[0].strip().lower().rstrip("`")
        if not tag or tag.isalpha():
            inner = lines[1].strip() if len(lines) > 1 else ""

    m = _SQL_START_RE.search(inner)
    if m:
        inner = inner[m.start():]

    return inner.strip()


def _post_openai_compatible(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not config.LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY 未设置，请在 .env 中配置")

    base_url = config.LLM_BASE_URL.strip() or "https://api.openai.com"
    url = base_url.rstrip("/") + endpoint

    headers = {
        "Authorization": f"Bearer {config.LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


def _call_openai(prompt: str, max_tokens: int = 2048, model: str = "gpt-3.5-turbo") -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    data = _post_openai_compatible("/v1/chat/completions", payload)
    content = data["choices"][0]["message"]["content"]
    return _normalize_response_text(content)


def _call_deepseek(prompt: str, max_tokens: int = 2048, model: str = "deepseek-v4-flash") -> str:
    base_url = config.LLM_BASE_URL.strip() or "https://api.deepseek.com"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    data = _post_openai_compatible("/v1/chat/completions", payload)
    content = data["choices"][0]["message"]["content"]
    return _normalize_response_text(content)


def _call_local(prompt: str, max_tokens: int = 2048) -> str:
    return (
        "--LOCAL LLM 模拟输出--\n"
        "请将 LLM_PROVIDER 设置为 openai 或 deepseek，并提供有效的 LLM_API_KEY，"
        "或实现本地模型调用逻辑。"
    )


def call_llm(prompt: str, max_tokens: int = 2048, model: str | None = None) -> str:
    provider = config.LLM_PROVIDER.strip().lower().replace(" ", "")
    if provider == "openai":
        return _call_openai(prompt, max_tokens=max_tokens, model=model or "gpt-3.5-turbo")
    if provider == "deepseek":
        return _call_deepseek(prompt, max_tokens=max_tokens, model=model or "deepseek-v4-flash")
    if provider == "local":
        return _call_local(prompt, max_tokens=max_tokens)

    raise ValueError(
        f"不支持的 LLM_PROVIDER: {provider}. 当前支持: openai, deepseek, local"
    )
