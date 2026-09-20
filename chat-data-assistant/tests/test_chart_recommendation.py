"""ai.chart_recommendation 单元测试：JSON 解析、推荐校验、启发式兜底。

无 pytest 依赖，可直接运行：
    venv\\Scripts\\python.exe tests\\test_chart_recommendation.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

import ai.chart_recommendation as cr
from ai.chart_recommendation import (
    _extract_json, _normalize_rec, _valid_rec, _fallback_recommendation,
    recommend_chart,
)


# ── _extract_json ──

def test_extract_json_plain():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_fenced():
    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_with_surrounding_text():
    assert _extract_json('好的，结果如下 {"a": 1} 完毕') == {"a": 1}


def test_extract_json_invalid():
    assert _extract_json("not json at all") is None


# ── _normalize_rec ──

def test_normalize_rec_valid():
    rec = _normalize_rec({"chart_type": "Bar", "x_col": "cat", "y_col": "val"})
    assert rec["chart_type"] == "bar" and rec["x_col"] == "cat"


def test_normalize_rec_requires_x():
    assert _normalize_rec({"chart_type": "bar", "x_col": "", "y_col": "v"}) is None


def test_normalize_rec_requires_y_unless_auto():
    assert _normalize_rec({"chart_type": "bar", "x_col": "c", "y_col": ""}) is None
    auto = _normalize_rec({"chart_type": "heatmap", "x_col": "c", "y_col": ""})
    assert auto and auto["chart_type"] == "heatmap"


def test_normalize_rec_keeps_z_col():
    rec = _normalize_rec({"chart_type": "scatter3d", "x_col": "a",
                          "y_col": "b", "z_col": "c"})
    assert rec["z_col"] == "c"


# ── _valid_rec ──

DF = pd.DataFrame({"cat": ["a", "b", "a"], "val": [1, 2, 3]})


def test_valid_bar_ok():
    assert _valid_rec(DF, {"chart_type": "bar", "x_col": "cat", "y_col": "val"})


def test_invalid_chart_type():
    assert not _valid_rec(DF, {"chart_type": "donut", "x_col": "cat", "y_col": "val"})


def test_bar_text_y_invalid():
    assert not _valid_rec(DF, {"chart_type": "bar", "x_col": "val", "y_col": "cat"})


def test_scatter_same_axis_invalid():
    assert not _valid_rec(DF, {"chart_type": "scatter", "x_col": "val", "y_col": "val"})


def test_missing_column_invalid():
    assert not _valid_rec(DF, {"chart_type": "bar", "x_col": "nope", "y_col": "val"})


def test_pie_too_many_categories_invalid():
    df8 = pd.DataFrame({"cat": [f"c{i}" for i in range(8)], "val": list(range(8))})
    assert not _valid_rec(df8, {"chart_type": "pie", "x_col": "cat", "y_col": "val"})
    assert _valid_rec(DF, {"chart_type": "pie", "x_col": "cat", "y_col": "val"})


def test_heatmap_needs_two_numeric():
    assert not _valid_rec(DF, {"chart_type": "heatmap", "x_col": "", "y_col": ""})
    df2 = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    assert _valid_rec(df2, {"chart_type": "heatmap", "x_col": "", "y_col": ""})


def test_histogram_requires_numeric_x():
    assert _valid_rec(DF, {"chart_type": "histogram", "x_col": "val", "y_col": ""})
    assert not _valid_rec(DF, {"chart_type": "histogram", "x_col": "cat", "y_col": ""})


def test_scatter3d_requires_three_numeric():
    assert not _valid_rec(DF, {"chart_type": "scatter3d", "x_col": "cat", "y_col": "val"})
    df3 = pd.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6]})
    assert _valid_rec(df3, {"chart_type": "scatter3d", "x_col": "a", "y_col": "b", "z_col": "c"})


def test_bubble_requires_numeric_xy():
    assert not _valid_rec(DF, {"chart_type": "bubble", "x_col": "cat", "y_col": "val"})
    df2 = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    assert _valid_rec(df2, {"chart_type": "bubble", "x_col": "a", "y_col": "b"})


# ── _fallback_recommendation ──

def test_fallback_pie_single_cat_single_numeric():
    rec = _fallback_recommendation(DF)
    assert rec["chart_type"] == "pie" and rec["x_col"] == "cat" and rec["y_col"] == "val"


def test_fallback_bar_multi_numeric():
    df = pd.DataFrame({"cat": ["a", "b"], "v1": [1, 2], "v2": [3, 4]})
    assert _fallback_recommendation(df)["chart_type"] == "bar"


def test_fallback_bar_many_categories():
    df = pd.DataFrame({"cat": [f"c{i}" for i in range(10)], "val": list(range(10))})
    assert _fallback_recommendation(df)["chart_type"] == "bar"


def test_fallback_scatter_two_numeric():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    rec = _fallback_recommendation(df)
    assert rec["chart_type"] == "scatter"


def test_fallback_histogram_single_numeric():
    df = pd.DataFrame({"a": [1, 2, 3]})
    rec = _fallback_recommendation(df)
    assert rec["chart_type"] == "histogram" and rec["y_col"] == ""


def test_fallback_none_cases():
    assert _fallback_recommendation(pd.DataFrame()) is None
    assert _fallback_recommendation(pd.DataFrame({"t": ["a", "b"]})) is None


# ── recommend_chart（monkeypatch LLM）──

def _with_llm(raw, fn):
    original = cr.call_llm_raw
    cr.call_llm_raw = lambda *a, **k: raw
    try:
        return fn()
    finally:
        cr.call_llm_raw = original


def test_recommend_chart_uses_llm_result():
    raw = '{"chart_type": "bar", "x_col": "cat", "y_col": "val", "reason": "r"}'
    rec = _with_llm(raw, lambda: recommend_chart(DF, "q", "sql"))
    assert rec["chart_type"] == "bar" and rec["x_col"] == "cat"


def test_recommend_chart_invalid_falls_back():
    rec = _with_llm("garbage", lambda: recommend_chart(DF, "q", "sql"))
    assert rec["chart_type"] == "pie"


def test_recommend_chart_llm_exception_falls_back():
    def boom(*a, **k):
        raise RuntimeError("network down")
    original = cr.call_llm_raw
    cr.call_llm_raw = boom
    try:
        rec = recommend_chart(DF, "q", "sql")
    finally:
        cr.call_llm_raw = original
    assert rec is not None and rec["chart_type"] == "pie"


def test_recommend_chart_empty_df():
    assert recommend_chart(pd.DataFrame(), "q", "sql") is None


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
