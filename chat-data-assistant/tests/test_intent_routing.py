"""意图路由（chart/data/chat）单元测试。

覆盖：
- extract_intent 解析与缺省行为
- to_sql_with_correction 的 chat 快速返回 / 意图透传
- pipeline.run_query 按 intent 路由与问数模式批量数据兜底拦截

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


# ── pipeline 路由 ──

def _run_pipeline(outcome):
    import api.pipeline as pl

    original = pl.to_sql_with_correction
    pl.to_sql_with_correction = lambda **kw: outcome
    try:
        return pl.run_query(schema_summary="s", history=[], question="q",
                            session_llm={}, lang="zh")
    finally:
        pl.to_sql_with_correction = original


def test_pipeline_data_intent_returns_stats_table():
    res = _run_pipeline(QueryOutcome(sql="SELECT MAX(a) FROM t",
                                     df=pd.DataFrame({"max_a": [1]}),
                                     error=None, intent="data", message=None))
    assert res["intent"] == "data"
    assert res["answer"] is None, "问数模式不再生成 LLM 文字解读"
    assert res["recommendation"] is None
    assert res["columns"] == ["max_a"] and res["row_count"] == 1


def test_pipeline_data_single_row_multi_col_passes():
    res = _run_pipeline(QueryOutcome(sql="SELECT MAX(a), MIN(a) FROM t",
                                     df=pd.DataFrame({"max": [9], "min": [1]}),
                                     error=None, intent="data", message=None))
    assert res["answer"] is None
    assert res["row_count"] == 1


def test_pipeline_data_bulk_sql_is_refused():
    """无聚合函数的 data SQL 视为批量拉取明细数据，应拒绝并清空数据。"""
    res = _run_pipeline(QueryOutcome(sql="SELECT a, b FROM t",
                                     df=pd.DataFrame({"a": [1, 2], "b": [3, 4]}),
                                     error=None, intent="data", message=None))
    assert res["answer"], "无聚合 SQL 应被兜底拦截"
    assert "抱歉" in res["answer"] and "批量" in res["answer"]
    assert res["columns"] == [] and res["rows"] == [] and res["row_count"] == 0, \
        "拒绝时不得向客户端返回任何明细数据"


def test_pipeline_data_multi_row_result_is_refused():
    """GROUP BY 等多行结果同样视为批量操作，应拒绝。"""
    res = _run_pipeline(QueryOutcome(
        sql="SELECT p_type, AVG(x) FROM t GROUP BY p_type",
        df=pd.DataFrame({"p_type": ["a", "b"], "avg_x": [1.0, 2.0]}),
        error=None, intent="data", message=None))
    assert res["answer"] and "抱歉" in res["answer"]
    assert res["columns"] == [] and res["row_count"] == 0


def test_pipeline_data_agg_in_subquery_passes():
    sql = "SELECT * FROM (SELECT MAX(x) AS m FROM t) sub"
    res = _run_pipeline(QueryOutcome(sql=sql, df=pd.DataFrame({"m": [1]}),
                                     error=None, intent="data", message=None))
    assert res["answer"] is None
    assert res["columns"] == ["m"]


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
