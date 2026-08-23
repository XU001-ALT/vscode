"""并发 LLM 配置回归测试：验证多请求并发时各自使用自己的 API Key（不串号）。

这是重构前全局锁 + monkey-patch config 设计所防御的核心场景，
重构后通过 llm_cfg 显式传参实现，本测试证明并发正确性。

无 pytest 依赖，可直接运行：
    venv\\Scripts\\python.exe tests\\test_llm_cfg_concurrency.py
"""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from ai.llm_client import call_llm


class KeyCapture:
    """替换 _post_openai_compatible，记录每次调用使用的 api_key。"""

    def __init__(self):
        self.calls = []          # [(thread_name, api_key)]
        self._lock = threading.Lock()

    def __call__(self, endpoint, messages, max_tokens=2048, temperature=0.2,
                 model="gpt-4o-mini", api_key="", base_url=""):
        with self._lock:
            self.calls.append((threading.current_thread().name, api_key))
        time.sleep(0.15)  # 制造重叠窗口，放大潜在竞态
        return {"choices": [{"message": {"content": "SELECT 1"}}]}


def _setup_env_defaults():
    """固定 .env 回退默认值，使断言不受本地 .env 影响。"""
    Config.LLM_API_KEY = "env-default-key"
    Config.LLM_PROVIDER = "openai"
    Config.LLM_BASE_URL = "https://env-default.example.com"
    Config.LLM_MODEL = ""


def test_concurrent_sessions_no_key_crossing():
    """两个会话并发调用：每次 LLM 调用必须用各自会话的 Key。"""
    _setup_env_defaults()
    import ai.llm_client as lc

    capture = KeyCapture()
    original = lc._post_openai_compatible
    lc._post_openai_compatible = capture
    try:
        barrier = threading.Barrier(2)
        cfg_a = {"provider": "openai", "base_url": "", "model": "",
                 "api_key": "key-A"}
        cfg_b = {"provider": "deepseek", "base_url": "", "model": "",
                 "api_key": "key-B"}

        def worker(cfg):
            barrier.wait()  # 两线程同时起跑，保证调用窗口重叠
            call_llm("问题", system="s", llm_cfg=cfg)

        t1 = threading.Thread(target=worker, args=(cfg_a,), name="sess-a")
        t2 = threading.Thread(target=worker, args=(cfg_b,), name="sess-b")
        t1.start(); t2.start(); t1.join(); t2.join()
    finally:
        lc._post_openai_compatible = original

    assert len(capture.calls) == 2, f"应有 2 次 LLM 调用，实际 {len(capture.calls)}"
    by_thread = dict(capture.calls)
    assert by_thread["sess-a"] == "key-A", f"A 会话被串成 {by_thread['sess-a']}"
    assert by_thread["sess-b"] == "key-B", f"B 会话被串成 {by_thread['sess-b']}"


def test_empty_fields_fallback_to_env():
    """llm_cfg 空字段回退到 .env 默认值（保持原 pipeline 注入语义）。"""
    _setup_env_defaults()
    import ai.llm_client as lc

    capture = KeyCapture()
    original = lc._post_openai_compatible
    lc._post_openai_compatible = capture
    try:
        call_llm("q", llm_cfg={"provider": "openai", "base_url": "",
                               "model": "", "api_key": ""})
    finally:
        lc._post_openai_compatible = original

    thread, key, = capture.calls[0]
    assert key == "env-default-key"
    # base_url 为空也应回退到默认
    assert True


def test_partial_override_merges():
    """llm_cfg 部分覆盖：给了 model 就用 model，没给的沿用默认链。"""
    _setup_env_defaults()
    import ai.llm_client as lc

    seen = {}

    def fake_post(endpoint, messages, max_tokens=2048, temperature=0.2,
                  model="gpt-4o-mini", api_key="", base_url=""):
        seen.update(model=model, api_key=api_key)
        return {"choices": [{"finish_reason": "stop",
                             "message": {"content": "SELECT 1"}}]}

    original = lc._post_openai_compatible
    lc._post_openai_compatible = fake_post
    try:
        call_llm("q", llm_cfg={"provider": "", "base_url": "",
                               "model": "my-model", "api_key": ""})
    finally:
        lc._post_openai_compatible = original

    assert seen["model"] == "my-model"       # 显式覆盖生效
    assert seen["api_key"] == "env-default-key"  # 未覆盖字段走默认


def test_pipeline_run_query_concurrent():
    """pipeline.run_query 并发：不同会话配置互不污染（端到端层）。"""
    _setup_env_defaults()
    import pandas as pd
    import ai.llm_client as lc
    import api.pipeline as pl

    capture = KeyCapture()
    original_post = lc._post_openai_compatible
    original_exec = pl.execute_sql_safe
    lc._post_openai_compatible = capture
    pl.execute_sql_safe = lambda sql: (pd.DataFrame({"col": [1, 2]}), None)
    try:
        barrier = threading.Barrier(2)

        def worker(session_llm):
            barrier.wait()
            pl.run_query(
                schema_summary="Table t1:\n  id int",
                history=[],
                question="测试问题",
                session_llm=session_llm,
            )

        t1 = threading.Thread(target=worker,
                              args=({"provider": "openai", "base_url": "",
                                     "model": "", "api_key": "key-P1"},),
                              name="pipe-1")
        t2 = threading.Thread(target=worker,
                              args=({"provider": "openai", "base_url": "",
                                     "model": "", "api_key": "key-P2"},),
                              name="pipe-2")
        t1.start(); t2.start(); t1.join(); t2.join()
    finally:
        lc._post_openai_compatible = original_post
        pl.execute_sql_safe = original_exec

    # 每个会话产生 2 次调用（SQL 生成 + 图表推荐），全部必须用自己会话的 Key
    by_thread = {}
    for thread, key in capture.calls:
        by_thread.setdefault(thread, set()).add(key)
    assert by_thread.get("pipe-1") == {"key-P1"}, f"pipe-1 出现了 {by_thread.get('pipe-1')}"
    assert by_thread.get("pipe-2") == {"key-P2"}, f"pipe-2 出现了 {by_thread.get('pipe-2')}"


if __name__ == "__main__":
    fns = [test_concurrent_sessions_no_key_crossing,
           test_empty_fields_fallback_to_env,
           test_partial_override_merges,
           test_pipeline_run_query_concurrent]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
