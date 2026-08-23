"""意图路由（chart/data/chat）单元测试。

覆盖：
- extract_intent 解析与缺省行为
- to_sql_with_correction 的 chat 快速返回 / 意图透传
- summarize_result 的 grounded prompt 与降级
- pipeline.run_query 按 intent + 开关路由

无 pytest 依赖，可直接运行：
    venv\\Scripts\\python.exe tests\\test_intent_routing.py
"""
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from ai.text_to_sql import QueryOutcome, extract_intent, to_sql_with_correction


# ── extract_intent ──

def test_intent_chart():
    assert extract_intent("INTENT: chart\n```sql\nSELECT 1\n```") == "chart"


def test_intent_data_case_insensitive():
    assert extract_intent("intent: DATA\nSELECT 1") == "data"


def test_intent_chat():
    assert extract_intent("INTENT: chat\n你好") == "chat"


def test_intent_missing_defaults_chart():
    assert extract_intent("```sql\nSELECT 1\n```") == "chart"
    assert extract_intent("") == "chart"
    assert extract_intent(None) == "chart"


# ── to_sql_with_correction ──

class _FakeExec:
    """记录调用并返回预设结果的执行函数。"""

    def __init__(self, err=None):
        self.calls = []
        self.err = err

    def __call__(self, sql):
        self.calls.append(sql)
        return pd.DataFrame({"col": [1, 2]}), self.err


def _with_llm_reply(reply, fn):
    """临时替换 ai.text_to_sql.call_llm_raw 后执行 fn()。"""
    import ai.text_to_sql as tts
    original = tts.call_llm_raw
    tts.call_llm_raw = lambda *a, **kw: reply
    try:
        return fn()
    finally:
        tts.call_llm_raw = original


def test_chat_intent_skips_sql_and_execution():
    exec_fn = _FakeExec()
    reply = ("INTENT: chat\n"
             "你好！我是数据库助手，只能帮你查询数据。")

    def run():
        return to_sql_with_correction(
            schema_summary="Table t1:\n  id int",
            chat_history=[], user_query="你好",
            execute_fn=exec_fn,
        )

    outcome = _with_llm_reply(reply, run)
    assert isinstance(outcome, QueryOutcome)
    assert outcome.intent == "chat"
    assert outcome.sql == ""
    assert outcome.error is None
    assert "数据库助手" in outcome.message
    assert exec_fn.calls == [], "chat 意图不应执行任何 SQL"


def test_chart_intent_executes_and_returns_df():
    exec_fn = _FakeExec()
    reply = "INTENT: chart\n```sql\nSELECT 1 AS a\n```\n说明"

    def run():
        return to_sql_with_correction(
            schema_summary="Table t1:\n  id int",
            chat_history=[], user_query="画图",
            execute_fn=exec_fn,
        )

    outcome = _with_llm_reply(reply, run)
    assert outcome.intent == "chart"
    assert outcome.error is None
    assert outcome.df is not None and len(outcome.df) == 2
    assert exec_fn.calls == ["SELECT 1 AS a"]


def test_data_intent_passthrough():
    exec_fn = _FakeExec()
    reply = "INTENT: data\n```sql\nSELECT COUNT(*) FROM t1\n```"

    def run():
        return to_sql_with_correction(
            schema_summary="Table t1:\n  id int",
            chat_history=[], user_query="有多少条",
            execute_fn=exec_fn,
        )

    outcome = _with_llm_reply(reply, run)
    assert outcome.intent == "data"
    assert outcome.error is None and outcome.df is not None


def test_missing_intent_still_executes_as_chart():
    exec_fn = _FakeExec()

    def run():
        return to_sql_with_correction(
            schema_summary="Table t1:\n  id int",
            chat_history=[], user_query="q",
            execute_fn=exec_fn,
        )

    # 无 INTENT 标记、无围栏的裸 SELECT 也应被解析执行
    outcome = _with_llm_reply("SELECT 1 AS a", run)
    assert outcome.intent == "chart"
    assert outcome.df is not None


def test_busy_error_keeps_intent():
    exec_fn = _FakeExec(err="连接池已满，请稍后重试")
    reply = "INTENT: data\n```sql\nSELECT 1\n```"

    def run():
        return to_sql_with_correction(
            schema_summary="Table t1:\n  id int",
            chat_history=[], user_query="q",
            execute_fn=exec_fn,
        )

    outcome = _with_llm_reply(reply, run)
    assert outcome.intent == "data"
    assert "连接池已满" in outcome.error
    assert len(exec_fn.calls) == 1, "过载错误不应触发 LLM 纠错循环"


# ── summarize_result ──

def test_summarize_grounds_prompt_and_returns_text():
    import ai.result_summary as rs

    captured = {}

    def fake_raw(prompt, max_tokens=1024, temperature=0.2, llm_cfg=None):
        captured["prompt"] = prompt
        captured["cfg"] = llm_cfg
        return "共 2 条记录，col 值为 1 和 2。"

    original = rs.call_llm_raw
    rs.call_llm_raw = fake_raw
    try:
        df = pd.DataFrame({"name": ["MgH2", "很长的" * 40], "val": [1.5, 2]})
        ans = rs.summarize_result(df, "有哪些样本？", "SELECT ...",
                                  lang="en", llm_cfg={"api_key": "k-x"})
    finally:
        rs.call_llm_raw = original

    assert ans and "2 条记录" in ans
    assert "MgH2" in captured["prompt"]
    assert "Answer in English" in captured["prompt"], "en 语言指令缺失"
    assert "编造" in captured["prompt"], "grounded 约束缺失"
    assert captured["cfg"] == {"api_key": "k-x"}
    # 长文本单元格应被截断
    assert "…" in captured["prompt"]


def test_summarize_empty_df_returns_none():
    import ai.result_summary as rs
    assert rs.summarize_result(pd.DataFrame(), "q", "s") is None


# ── pipeline 路由 ──

def _run_pipeline(outcome, enable_summary=True):
    import api.pipeline as pl
    from config import Config

    df = outcome.df if isinstance(outcome.df, pd.DataFrame) else None
    original_tts = pl.to_sql_with_correction
    original_flag = Config.ENABLE_AI_SUMMARY
    pl.to_sql_with_correction = lambda **kw: outcome
    Config.ENABLE_AI_SUMMARY = enable_summary
    try:
        return pl.run_query(schema_summary="s", history=[], question="q",
                            session_llm={}, lang="zh")
    finally:
        pl.to_sql_with_correction = original_tts
        Config.ENABLE_AI_SUMMARY = original_flag


def test_pipeline_data_intent_returns_answer():
    res = _run_pipeline(QueryOutcome(sql="SELECT 1", df=pd.DataFrame({"a": [1]}),
                                     error=None, intent="data", message=None))
    assert res["intent"] == "data"
    assert res["answer"] is not None, "data 意图应生成解读（开关默认开）"
    assert res["recommendation"] is None


def test_pipeline_chart_intent_returns_recommendation():
    res = _run_pipeline(QueryOutcome(sql="SELECT 1", df=pd.DataFrame({"a": [1]}),
                                     error=None, intent="chart", message=None))
    assert res["intent"] == "chart"
    assert res["recommendation"] is not None
    assert res["answer"] is None


def test_pipeline_chat_intent_answer_only():
    res = _run_pipeline(QueryOutcome(sql="", df=None, error=None,
                                     intent="chat", message="你好呀"))
    assert res["intent"] == "chat"
    assert res["answer"] == "你好呀"
    assert res["columns"] == [] and res["row_count"] == 0


def test_pipeline_summary_disabled_data_falls_back_to_table():
    res = _run_pipeline(QueryOutcome(sql="SELECT 1", df=pd.DataFrame({"a": [1]}),
                                     error=None, intent="data", message=None),
                        enable_summary=False)
    assert res["intent"] == "data"
    assert res["answer"] is None
    assert res["recommendation"] is None, "总结关闭时问数模式仅返回表格"


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
