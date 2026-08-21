"""LLM 配置接口（会话级，API Key 仅存服务端内存）。"""
from fastapi import APIRouter
from pydantic import BaseModel

import api.sessions as sessions
from config import config

router = APIRouter(prefix="/api")


class LlmConfig(BaseModel):
    session_id: str
    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None


def _mask(key: str, visible: int = 6) -> str:
    if not key or len(key) <= visible * 2 + 2:
        return key
    return f"{key[:visible]}***{key[-visible:]}"


@router.put("/config/llm")
def set_llm_config(body: LlmConfig):
    sessions.set_llm_config(
        body.session_id,
        provider=body.provider,
        base_url=body.base_url,
        model=body.model,
        api_key=body.api_key,
    )
    return get_llm_config(body.session_id)


@router.get("/config/llm/{session_id}")
def get_llm_config(session_id: str):
    llm = sessions.get(session_id)["llm"]
    effective_key = llm["api_key"] or config.LLM_API_KEY
    return {
        "provider": llm["provider"] or config.LLM_PROVIDER,
        "base_url": llm["base_url"] or config.LLM_BASE_URL,
        "model": llm["model"] or config.LLM_MODEL,
        "has_custom_key": bool(llm["api_key"]),
        "key_masked": _mask(effective_key) if effective_key else "",
    }


@router.delete("/config/llm/{session_id}")
def clear_llm_config(session_id: str):
    sessions.clear_llm_config(session_id)
    return {"ok": True}
