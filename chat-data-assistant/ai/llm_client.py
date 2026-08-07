"""LLM 调用封装，支持 OpenAI、DeepSeek 和本地开发模式。

安全设计:
- API Key 优先从服务端私有存储读取（不依赖 session_state，避免 WebSocket 泄漏）
- 回退顺序: 服务端私有存储 > 侧边栏 session_state 遗留值 > .env 默认值
- 错误消息中的 Key 自动脱敏
"""
import re
from typing import Any

import httpx
from config import config

_SQL_START_RE = re.compile(r"^\s*(select|with|explain|show|describe|desc)\b", re.IGNORECASE | re.MULTILINE)


def _get_effective_config() -> tuple[str, str, str, str]:
    """获取生效的 LLM 配置。

    优先级（由高到低）:
    1. 服务端私有存储（侧边栏输入，安全，不进入 WebSocket）
    2. 侧边栏 session_state 遗留值（兼容旧代码）
    3. .env / Streamlit secrets 默认值
    """
    api_key = ""
    provider = ""
    base_url = ""
    model = ""

    try:
        import streamlit as st
        # 首选：服务端私有存储（不经过 WebSocket）
        try:
            from core.secrets import get_effective_key, get_effective_base_url, get_effective_model
            api_key = get_effective_key()
            base_url = get_effective_base_url()
            model = get_effective_model()
        except ImportError:
            pass

        # 回退：session_state 中的 provider（非敏感，可以留在 session_state）
        provider = st.session_state.get('llm_provider', '').strip()

        # 如果服务端存储没有 key，回退到 session_state（兼容旧代码）
        if not api_key:
            api_key = st.session_state.get('llm_api_key', '').strip()
    except Exception:
        pass

    # 最终回退：.env 配置
    if not api_key:
        api_key = config.LLM_API_KEY
    if not provider:
        provider = config.LLM_PROVIDER
    if not base_url:
        base_url = config.LLM_BASE_URL
    if not model:
        model = config.LLM_MODEL

    return api_key, provider, base_url, model


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
    api_key: str = "",
    base_url: str = "",
) -> dict[str, Any]:
    """统一的 OpenAI 兼容 API 调用。"""
    api_key = api_key or config.LLM_API_KEY
    if not api_key:
        raise RuntimeError("LLM_API_KEY 未设置，请在侧边栏填写或 .env 中配置")

    base_url = (base_url or config.LLM_BASE_URL).strip() or "https://api.openai.com"
    url = base_url.rstrip("/") + endpoint

    headers = {
        "Authorization": f"Bearer {api_key}",
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
    api_key, provider, base_url, default_model = _get_effective_config()

    provider = provider.strip().lower().replace(" ", "")
    model = model or default_model or None
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
        api_key=api_key,
        base_url=base_url,
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
    api_key, provider, base_url, default_model = _get_effective_config()

    provider = provider.strip().lower().replace(" ", "")
    model = model or default_model or None
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
        api_key=api_key,
        base_url=base_url,
    )
    return data["choices"][0]["message"]["content"].strip()
