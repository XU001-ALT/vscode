"""LLM 调用封装，支持 OpenAI、DeepSeek 和本地开发模式。

安全设计:
- 会话级配置通过 llm_cfg 参数显式传入（线程安全，可并发）
- API Key 优先从服务端私有存储读取（不依赖 session_state，避免 WebSocket 泄漏）
- 回退顺序: 显式 llm_cfg > 服务端私有存储 > 侧边栏 session_state 遗留值 > .env 默认值
- 错误消息中的 Key 自动脱敏
"""
import re
from typing import Any

import httpx
from config import config

_SQL_START_RE = re.compile(r"^\s*(select|with|explain|show|describe|desc)\b", re.IGNORECASE | re.MULTILINE)


def _infer_provider_from_url(base_url: str) -> str:
    """根据 base_url 自动推断 provider（provider 为空时的兜底）。"""
    url = base_url.lower()
    if "openai.com" in url:
        return "openai"
    if "deepseek" in url:
        return "deepseek"
    if "anthropic" in url or "claude" in url:
        return "anthropic"
    if "dashscope" in url or "aliyun" in url or "qwen" in url:
        return "openai"  # 通义千问兼容 OpenAI 协议
    if "moonshot" in url:
        return "openai"  # Kimi 兼容 OpenAI 协议
    if "baichuan" in url:
        return "openai"
    if "closeai" in url:
        return "openai"  # CloseAI 中转兼容 OpenAI 协议
    return ""


def _get_effective_config(llm_cfg: dict | None = None) -> tuple[str, str, str, str]:
    """获取生效的 LLM 配置。

    优先级（由高到低）:
    0. 显式传入的会话级配置 llm_cfg（FastAPI 管道传参，非空字段覆盖，
       空/缺失字段沿用默认链——与原 pipeline 的注入语义一致）
    1. 服务端私有存储（侧边栏输入，安全，不进入 WebSocket）
    2. 侧边栏 session_state 遗留值（兼容旧代码）
    3. .env / Streamlit secrets 默认值
    """
    api_key, provider, base_url, model = _get_fallback_config()
    cfg = llm_cfg or {}
    api_key = cfg.get("api_key") or api_key
    provider = cfg.get("provider") or provider
    base_url = cfg.get("base_url") or base_url
    model = cfg.get("model") or model
    # provider 仍为空时，从 base_url 自动推断（UI 保存时未传 provider 字段）
    if not provider and base_url:
        provider = _infer_provider_from_url(base_url)
    return api_key, provider, base_url, model


def _get_fallback_config() -> tuple[str, str, str, str]:
    """默认回退链的 LLM 配置（不含会话级显式配置）。"""
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


def _strip_code_fence(block: str) -> str:
    """去掉代码块首行的语言标签（sql/python 等）。"""
    lines = block.strip().split("\n", 1)
    if lines:
        tag = lines[0].strip().lower().rstrip("`")
        if not tag or tag.isalpha():
            return lines[1].strip() if len(lines) > 1 else ""
    return block.strip()


def _normalize_response_text(text: str) -> str:
    """从 LLM 回复中提取纯 SQL 文本。

    处理策略:
    1. 如果包含 ``` 代码块，依次检查每个代码块（含末尾未闭合的块），
       取第一个含 SELECT/WITH 等只读语句的块——避免模型先输出说明性
       代码块时取错块，或输出被截断时取到残片
    2. 去掉代码块的语言标签（sql/python 等）
    3. 从首个以 SELECT/WITH 等开头的行开始截取
    """
    text = text.strip()

    if "```" in text:
        pieces = text.split("```")
        # 成对代码块的内容位于奇数下标；未闭合的最后一个块同样是奇数下标
        candidates = [_strip_code_fence(pieces[i]) for i in range(1, len(pieces), 2)]
    else:
        candidates = [_strip_code_fence(text)]

    for inner in candidates:
        m = _SQL_START_RE.search(inner)
        if m:
            return inner[m.start():].strip()

    # 没有任何代码块包含只读语句：回退为对整段文本按原逻辑处理
    fallback = _strip_code_fence(text)
    m = _SQL_START_RE.search(fallback)
    if m:
        fallback = fallback[m.start():]
    return fallback.strip()


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
    llm_cfg: dict | None = None,
) -> str:
    """通用 LLM 调用入口。

    Args:
        prompt: user prompt 文本
        system: 可选的 system prompt
        max_tokens: 最大生成 token 数
        model: 模型名，默认根据 provider 自动选择
        temperature: 生成温度
        llm_cfg: 会话级 LLM 配置 {provider, base_url, model, api_key}，
                 非空字段优先于全局默认；传 None 走原回退链

    Returns:
        LLM 回复的纯文本（已提取 SQL）
    """
    api_key, provider, base_url, default_model = _get_effective_config(llm_cfg)

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
    choice = (data.get("choices") or [{}])[0]
    if choice.get("finish_reason") == "length":
        # 输出被截断：与其拿半截 SQL 去执行再触发多轮纠错（更慢更贵），
        # 不如快速失败并给出可操作提示
        raise RuntimeError(
            "LLM 输出因长度限制被截断，未能生成完整 SQL。"
            "请把问题拆得更具体一些，或在配置中增大 LLM_MAX_TOKENS。"
        )
    content = (choice.get("message") or {}).get("content")
    if not content or not content.strip():
        raise RuntimeError("LLM 返回了空内容，请稍后重试或检查模型配置。")
    return _normalize_response_text(content)


def call_llm_raw(
    prompt: str,
    system: str | None = None,
    max_tokens: int = 2048,
    model: str | None = None,
    temperature: float = 0.2,
    llm_cfg: dict | None = None,
) -> str:
    """与 call_llm 相同，但返回 LLM 原始输出（不做 SQL 提取）。

    用于需要完整回复文本的场景（如纠错、推荐等）。
    """
    api_key, provider, base_url, default_model = _get_effective_config(llm_cfg)

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
