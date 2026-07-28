"""LLM 调用封装，支持 OpenAI、DeepSeek 和本地开发模式。"""
import re
from typing import Any

import httpx
from config import config

_SQL_START_RE = re.compile(r"^\s*(select|with|explain|show|describe|desc)\b", re.IGNORECASE | re.MULTILINE)


def _normalize_response_text(text: str) -> str:
    """从 LLM 回复中提取纯 SQL 文本。

    处理策略:
    1. 如果包含 ``` 代码块，优先取第一个代码块内容
    2. 去掉代码块的语言标签（sql/python 等）
    3. 如果剩余内容以 SELECT/WITH 等开头，直接使用
    """
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


def _post_openai_compatible(
    endpoint: str,
    messages: list[dict[str, str]],
    max_tokens: int = 2048,
    temperature: float = 0.2,
    model: str = "gpt-3.5-turbo",
) -> dict[str, Any]:
    """统一的 OpenAI 兼容 API 调用。"""
    if not config.LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY 未设置，请在 .env 中配置")

    base_url = config.LLM_BASE_URL.strip() or "https://api.openai.com"
    url = base_url.rstrip("/") + endpoint

    headers = {
        "Authorization": f"Bearer {config.LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    with httpx.Client(timeout=120.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


def _get_messages(system: str | None, user: str) -> list[dict[str, str]]:
    """构建 messages 列表，可选 system prompt。"""
    msgs: list[dict[str, str]] = []
    if system and system.strip():
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": user})
    return msgs


def call_llm(
    prompt: str,
    system: str | None = None,
    max_tokens: int = 2048,
    model: str | None = None,
    temperature: float = 0.2,
) -> str:
    """通用 LLM 调用入口。

    Args:
        prompt: user prompt 文本
        system: 可选的 system prompt
        max_tokens: 最大生成 token 数
        model: 模型名，默认根据 provider 自动选择
        temperature: 生成温度

    Returns:
        LLM 回复的纯文本（已提取 SQL）
    """
    provider = config.LLM_PROVIDER.strip().lower().replace(" ", "")
    model = model or config.LLM_MODEL or None
    max_tokens = max_tokens or config.LLM_MAX_TOKENS
    temperature = temperature if temperature != 0.2 else config.LLM_TEMPERATURE

    if provider == "openai":
        model = model or "gpt-4o-mini"
    elif provider == "deepseek":
        model = model or "deepseek-v4-flash"
    elif provider == "local":
        return (
            "--LOCAL LLM 模拟输出--\n"
            "请将 LLM_PROVIDER 设置为 openai 或 deepseek，并提供有效的 LLM_API_KEY，"
            "或实现本地模型调用逻辑。"
        )
    else:
        raise ValueError(
            f"不支持的 LLM_PROVIDER: {provider}. 当前支持: openai, deepseek, local"
        )

    data = _post_openai_compatible(
        endpoint="/v1/chat/completions",
        messages=_get_messages(system, prompt),
        max_tokens=max_tokens,
        temperature=temperature,
        model=model,
    )
    content = data["choices"][0]["message"]["content"]
    return _normalize_response_text(content)


def call_llm_raw(
    prompt: str,
    system: str | None = None,
    max_tokens: int = 2048,
    model: str | None = None,
    temperature: float = 0.2,
) -> str:
    """与 call_llm 相同，但返回 LLM 原始输出（不做 SQL 提取）。

    用于需要完整回复文本的场景（如纠错、推荐等）。
    """
    provider = config.LLM_PROVIDER.strip().lower().replace(" ", "")
    model = model or config.LLM_MODEL or None
    max_tokens = max_tokens or config.LLM_MAX_TOKENS
    temperature = temperature if temperature != 0.2 else config.LLM_TEMPERATURE

    if provider == "openai":
        model = model or "gpt-4o-mini"
    elif provider == "deepseek":
        model = model or "deepseek-v4-flash"
    elif provider == "local":
        return (
            "[LOCAL LLM 模拟] 未连接真实 LLM，请配置 LLM_PROVIDER 和 LLM_API_KEY。"
        )
    else:
        raise ValueError(
            f"不支持的 LLM_PROVIDER: {provider}. 当前支持: openai, deepseek, local"
        )

    data = _post_openai_compatible(
        endpoint="/v1/chat/completions",
        messages=_get_messages(system, prompt),
        max_tokens=max_tokens,
        temperature=temperature,
        model=model,
    )
    return data["choices"][0]["message"]["content"].strip()
