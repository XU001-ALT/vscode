"""tools.video.select 单元测试：推荐判定、排序与缺口检测（FR-007 / FR-010 / FR-011）。

无 pytest 依赖，可直接运行：
    venv\\Scripts\\python.exe tests\\test_video_select.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.video import select  # noqa: E402
from tools.video import settings as S  # noqa: E402


def _aesthetic(ok: bool = True, overlap: float = 0.0) -> dict:
    return {"no_label_overlap": ok, "no_text_truncation": ok, "axes_legend_complete": ok,
            "theme_consistent": ok, "max_overlap_ratio": overlap, "issues": [] if ok else ["x"]}


def _result(cid: str, *, points: int = 30, verdict: str = "chart_ok", source: str = "query",
            chart: str = "scatter", ok: bool = True, overlap: float = 0.0) -> dict:
    return {"id": cid, "source": source, "verdict": verdict, "data_points": points,
            "chart_type": chart, "aesthetics": _aesthetic(ok, overlap),
            "recommended": False, "rank": 0}


def test_recommended_requires_three_criteria():
    good = _result("good", points=30)
    too_few = _result("few", points=S.MIN_DATA_POINTS - 1)
    ugly = _result("ugly", ok=False)
    table = _result("table", verdict="table_only")
    for item in (good, too_few, ugly, table):
        assert select.is_recommended(item) is (item is good)


def test_threshold_boundary_is_inclusive():
    assert select.is_recommended(_result("edge", points=S.MIN_DATA_POINTS)) is True


def test_rank_is_sequential_and_zero_for_others():
    results = [_result("a", points=12), _result("b", points=40), _result("c", points=8)]
    select.rank_results(results, S.MIN_DATA_POINTS)
    by_id = {r["id"]: r for r in results}
    assert by_id["b"]["rank"] == 1 and by_id["a"]["rank"] == 2 and by_id["c"]["rank"] == 0
    assert by_id["c"]["recommended"] is False


def test_sort_prefers_more_points_then_less_overlap():
    results = [_result("small", points=12, overlap=0.0), _result("big", points=50, overlap=0.0),
               _result("same", points=12, overlap=0.01)]
    select.rank_results(results, S.MIN_DATA_POINTS)
    order = [r["id"] for r in sorted(results, key=lambda r: r["rank"] or 999)]
    assert order[:2] == ["big", "small"] and order[2] == "same"


def test_summary_counts_and_gap_detection():
    results = [
        _result("q1", points=30), _result("q2", points=25), _result("m1", points=32, source="manual"),
        _result("fail", verdict="failed", points=0),
    ]
    payload = select.rank_results(results, S.MIN_DATA_POINTS)
    summary = payload["summary"]
    assert summary["total"] == 4 and summary["chart_ok"] == 3 and summary["failed"] == 1
    assert summary["recommended"] == 3 and summary["manual_recommended"] == 1
    assert any("insufficient_qualified_scenes" in i for i in payload["issues"])
    assert not any("insufficient_manual_sources" in i for i in payload["issues"])


def test_gap_when_no_manual_sample():
    results = [_result(f"q{i}", points=20) for i in range(3)]
    payload = select.rank_results(results, S.MIN_DATA_POINTS)
    assert any("insufficient_manual_sources" in i for i in payload["issues"])


def test_aesthetics_passed_helper():
    assert select.aesthetics_passed(_aesthetic(True)) is True
    assert select.aesthetics_passed(_aesthetic(False)) is False
    assert select.aesthetics_passed(None) is False


def test_suggestions_for_each_failure_mode():
    table = _result("t", verdict="table_only", points=1)
    table["intent"] = "data"
    assert any("intent=data" in tip for tip in select.suggestions(table))

    few = _result("f", points=3)
    assert any("数据点" in tip for tip in select.suggestions(few))

    failed = {"id": "e", "verdict": "failed", "error_code": "llm_auth", "aesthetics": _aesthetic(False)}
    assert any("凭据" in tip for tip in select.suggestions(failed))
    assert select.suggestions(_result("ok", points=30)) == []


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
