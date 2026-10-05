"""tools.video.classify 单元测试：三态判定、图表类型、数据点数与错误码映射。

无 pytest 依赖，可直接运行：
    venv\\Scripts\\python.exe tests\\test_video_classify.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.video import classify  # noqa: E402

PROMPT = {"zh": "对比全部 PCT 测试的平台压力与放氢容量分布", "en": "Compare pressure against capacity"}


def _snapshot(**overrides) -> dict:
    data = {"has_plotly": False, "traces": [], "error_text": "", "answer_text": "",
            "record_count": None, "plate": None, "clip": None, "aesthetics": None, "elapsed_ms": 1200}
    data.update(overrides)
    return data


def _points(n: int, type_: str = "scatter", method: str = "plotly_points") -> list[dict]:
    return [{"type": type_, "points": n, "method": method, "mode": "markers"}]


def test_chart_ok_when_plotly_rendered():
    result = classify.classify(_snapshot(has_plotly=True, traces=_points(36)),
                               source="query", prompt=PROMPT)
    assert result["verdict"] == "chart_ok"
    assert result["chart_type"] == "scatter"
    assert result["data_points"] == 36 and result["data_points_method"] == "row_count"
    assert result["intent"] == "chart" and result["api_ok"] is True


def test_table_only_when_chat_answer_without_plotly():
    result = classify.classify(_snapshot(answer_text="我理解为一次普通提问。"),
                               source="query", prompt=PROMPT)
    assert result["verdict"] == "table_only" and result["intent"] == "chat"


def test_table_only_when_api_reports_single_row_data_intent():
    api = {"ok": True, "error_code": None, "intent": "data", "row_count": 1, "columns": ["total"]}
    result = classify.classify(_snapshot(answer_text="一共 128 条记录。"),
                               source="query", prompt=PROMPT, api=api)
    assert result["verdict"] == "table_only" and result["intent"] == "data"


def test_failed_on_error_text():
    result = classify.classify(_snapshot(error_text="API key 无效，请检查配置"),
                               source="query", prompt=PROMPT)
    assert result["verdict"] == "failed"
    assert result["error_code"] == "llm_auth"
    assert result["api_ok"] is False


def test_api_error_wins_over_missing_dom():
    api = {"ok": False, "error_code": "sql_failed", "intent": None, "row_count": 0, "columns": []}
    result = classify.classify(_snapshot(), source="query", prompt=PROMPT, api=api)
    assert result["verdict"] == "failed" and result["error_code"] == "sql_failed"


def test_few_points_still_chart_ok_but_not_recommended_by_select():
    result = classify.classify(_snapshot(has_plotly=True, traces=_points(3)),
                               source="query", prompt=PROMPT)
    assert result["verdict"] == "chart_ok" and result["data_points"] == 3


def test_cells_method_for_multi_column_charts():
    result = classify.classify(_snapshot(has_plotly=True,
                                         traces=[{"type": "heatmap", "points": 90, "method": "cells"}]),
                               source="query", prompt=PROMPT)
    assert result["chart_type"] == "heatmap" and result["data_points_method"] == "cells"


def test_chart_type_mapping():
    assert classify.normalize_chart_type([{"type": "scatter", "mode": "lines"}]) == "line"
    assert classify.normalize_chart_type([{"type": "scatter", "mode": "markers"}]) == "scatter"
    assert classify.normalize_chart_type([{"type": "parcoords"}]) == "parallel"
    assert classify.normalize_chart_type([{"type": "scatterpolar"}]) == "radar"
    assert classify.normalize_chart_type([{"type": "histogram"}]) == "histogram"
    assert classify.normalize_chart_type([]) is None


def test_manual_source_uses_plotter_record_count():
    snapshot = _snapshot(has_plotly=True, traces=_points(32), record_count=32)
    result = classify.classify(snapshot, source="manual", prompt=PROMPT,
                               manual_chart_type="bubble")
    assert result["source"] == "manual"
    assert result["chart_type"] == "bubble"
    assert result["data_points"] == 32 and result["data_points_method"] == "manual"


def test_error_code_from_text_variants():
    assert classify.error_code_from_text("请求超时，请稍后重试") == "llm_timeout"
    assert classify.error_code_from_text("connection refused") == "llm_conn"
    assert classify.error_code_from_text("数据库表结构尚未就绪") == "no_schema"
    assert classify.error_code_from_text("问题不能为空") == "empty_question"
    assert classify.error_code_from_text("something odd") == "unknown"
    assert classify.error_code_from_text("") is None


def test_error_excerpt_is_truncated_and_sanitized():
    long_error = "sk-abcdefghijklmnopqrstuvwx1234 " + "x" * 400
    result = classify.classify(_snapshot(error_text=long_error), source="query", prompt=PROMPT)
    assert len(result["error_excerpt"]) <= 200
    assert "sk-abcdefghijklmnopqrstuvwx1234" not in result["error_excerpt"]


def test_result_has_exactly_the_schema_fields():
    result = classify.classify(_snapshot(has_plotly=True, traces=_points(20)),
                               source="query", prompt=PROMPT)
    assert set(result) == {
        "id", "source", "prompt", "verdict", "intent", "chart_type", "data_points",
        "data_points_method", "api_ok", "error_code", "error_excerpt", "plate_path",
        "recommended", "rank", "capture_ms",
    }


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
