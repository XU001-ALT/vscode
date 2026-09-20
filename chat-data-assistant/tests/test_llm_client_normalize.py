"""ai.llm_client 单元测试：SQL 文本归一化、provider 推断、错误分支（不联网）。

无 pytest 依赖，可直接运行：
    venv\\Scripts\\python.exe tests\\test_llm_client_normalize.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ai.llm_client as lc
from ai.llm_client import (
    _normalize_response_text, _strip_code_fence,
    _infer_provider_from_url, _get_effective_config, _get_messages,
    call_llm,
)
from config import Config


# ── _strip_code_fence ──

def test_strip_code_fence_language_tag():
    assert _strip_code_fence("sql\nSELECT 1") == "SELECT 1"


def test_strip_code_fence_no_tag():
    assert _strip_code_fence("SELECT 1") == "SELECT 1"


# ── _normalize_response_text ──

def test_normalize_fenced_sql():
    assert _normalize_response_text("```sql\nSELECT 1 AS a\n```") == "SELECT 1 AS a"


def test_normalize_picks_sql_block_over_prose_block():
    text = "```\n说明文字\n```\n```sql\nSELECT 2\n```"
    assert _normalize_response_text(text) == "SELECT 2"


def test_normalize_plain_select_with_prefix_text():
    text = "好的，下面是查询：\nSELECT 3"
    assert _normalize_response_text(text).startswith("SELECT 3")


def test_normalize_unclosed_fence():
    assert _normalize_response_text("```sql\nSELECT 4").startswith("SELECT 4")


def test_normalize_empty_returns_empty():
    assert _normalize_response_text("   ") == ""


# ── provider 推断 ──

def test_infer_provider_from_url():
    assert _infer_provider_from_url("https://api.openai.com") == "openai"
    assert _infer_provider_from_url("https://api.deepseek.com") == "deepseek"
    assert _infer_provider_from_url("https://api.anthropic.com") == "anthropic"
    assert _infer_provider_from_url("https://dashscope.aliyuncs.com") == "openai"
    assert _infer_provider_from_url("https://unknown.example.com") == ""


def test_effective_config_infers_provider_when_absent():
    Config.LLM_PROVIDER = ""
    Config.LLM_BASE_URL = ""
    Config.LLM_MODEL = ""
    Config.LLM_API_KEY = ""
    _, provider, _, _ = _get_effective_config(
        {"provider": "", "base_url": "https://api.deepseek.com",
         "model": "", "api_key": "k"})
    assert provider == "deepseek"


def test_effective_config_explicit_provider_wins():
    Config.LLM_PROVIDER = ""
    _, provider, _, _ = _get_effective_config(
        {"provider": "openai", "base_url": "https://api.deepseek.com",
         "model": "", "api_key": "k"})
    assert provider == "openai"


def test_effective_config_overrides_model():
    Config.LLM_MODEL = "env-model"
    _, _, _, model = _get_effective_config(
        {"provider": "openai", "base_url": "", "model": "my-model", "api_key": ""})
    assert model == "my-model"


# ── _get_messages ──

def test_get_messages_with_system():
    msgs = _get_messages("sys", "user")
    assert msgs[0] == {"role": "system", "content": "sys"}
    assert msgs[1] == {"role": "user", "content": "user"}


def test_get_messages_without_system():
    assert _get_messages(None, "user") == [{"role": "user", "content": "user"}]
    assert _get_messages("   ", "user") == [{"role": "user", "content": "user"}]


# ── call_llm 错误分支（monkeypatch，不联网）──

def _with_post(fake, fn):
    original = lc._post_openai_compatible
    lc._post_openai_compatible = fake
    try:
        return fn()
    finally:
        lc._post_openai_compatible = original


def test_call_llm_success_extracts_sql():
    fake = lambda *a, **k: {"choices": [{"message": {"content": "```sql\nSELECT 9\n```"}}]}
    out = _with_post(fake, lambda: call_llm(
        "q", llm_cfg={"provider": "openai", "api_key": "k",
                      "base_url": "", "model": ""}))
    assert out == "SELECT 9"


def test_call_llm_truncation_raises():
    fake = lambda *a, **k: {"choices": [{"finish_reason": "length",
                                         "message": {"content": "SELECT"}}]}
    try:
        _with_post(fake, lambda: call_llm(
            "q", llm_cfg={"provider": "openai", "api_key": "k",
                          "base_url": "", "model": ""}))
        assert False, "截断应抛 RuntimeError"
    except RuntimeError as e:
        assert "截断" in str(e)


def test_call_llm_empty_content_raises():
    fake = lambda *a, **k: {"choices": [{"message": {"content": "  "}}]}
    try:
        _with_post(fake, lambda: call_llm(
            "q", llm_cfg={"provider": "openai", "api_key": "k",
                          "base_url": "", "model": ""}))
        assert False, "空内容应抛 RuntimeError"
    except RuntimeError as e:
        assert "空内容" in str(e)


def test_call_llm_unsupported_provider_raises():
    try:
        call_llm("q", llm_cfg={"provider": "weird", "api_key": "k",
                               "base_url": "", "model": ""})
        assert False, "未知 provider 应抛 ValueError"
    except ValueError as e:
        assert "weird" in str(e)


def test_call_llm_local_returns_simulation():
    out = call_llm("q", llm_cfg={"provider": "local", "api_key": "",
                                 "base_url": "", "model": ""})
    assert "LOCAL" in out


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
