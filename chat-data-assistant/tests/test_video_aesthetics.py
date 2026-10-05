"""tools.video.aesthetics 单元测试：交叠比、截断、坐标轴/图例、主题一致性（FR-009）。

无 pytest 依赖，可直接运行：
    venv\\Scripts\\python.exe tests\\test_video_aesthetics.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.video import aesthetics  # noqa: E402
from tools.video import settings as S  # noqa: E402


def _rect(x, y, w, h, kind="xtick", text="t"):
    return {"x": x, "y": y, "width": w, "height": h, "kind": kind, "text": text}


def _good_measured(**overrides) -> dict:
    data = {
        "found": True,
        "rects": [_rect(0, 0, 40, 12), _rect(60, 0, 40, 12), _rect(120, 0, 40, 12)],
        "truncations": [],
        "tickCount": {"x": 6, "y": 5},
        "legendItems": 1,
        "traceCount": 1,
        "has_xtitle": True,
        "has_ytitle": True,
        "app_lang": "zh",
        "paper_bgcolor": "rgba(0, 0, 0, 0)",
    }
    data.update(overrides)
    return data


def test_rect_intersection_and_ratio():
    a = aesthetics.Rect(0, 0, 10, 10)
    b = aesthetics.Rect(5, 5, 10, 10)
    c = aesthetics.Rect(20, 20, 5, 5)
    assert a.intersects(b) and not a.intersects(c)
    assert abs(aesthetics.overlap_ratio(a, b) - 0.25) < 1e-9      # 25 / 100
    assert aesthetics.overlap_ratio(a, c) == 0.0


def test_count_overlaps_threshold_boundary():
    left = aesthetics.Rect(0, 0, 100, 10)
    # 交叠 5% 恰好等于阈值 → 记为一对
    at_threshold = [left, aesthetics.Rect(95, 0, 100, 10)]
    over, worst = aesthetics.count_overlaps(at_threshold)
    assert over == 1 and abs(worst - S.MAX_OVERLAP_RATIO) < 1e-9
    # 交叠 4% → 通过
    below = [left, aesthetics.Rect(96, 0, 100, 10)]
    over2, _ = aesthetics.count_overlaps(below)
    assert over2 == 0


def test_find_truncations_reports_both_axes():
    items = [
        {"label": ".title", "text": "很长很长的标题", "sw": 220, "cw": 200, "sh": 20, "ch": 20},
        {"label": ".legend", "text": "图例", "sw": 40, "cw": 40, "sh": 40, "ch": 24},
        {"label": ".ok", "text": "正常", "sw": 40, "cw": 40, "sh": 20, "ch": 20},
    ]
    issues = aesthetics.find_truncations(items)
    assert len(issues) == 2
    assert any("横向" in i for i in issues) and any("纵向" in i for i in issues)


def test_count_oriented_overlaps_uses_page_ratios_and_threshold():
    pairs = [{"a": "t1", "b": "t2", "ratio": 0.377},
             {"a": "t3", "b": "t4", "ratio": 0.049},
             {"a": "t5", "b": "t6", "ratio": 0.0}]
    over, worst = aesthetics.count_oriented_overlaps(pairs)
    assert over == 1 and abs(worst - 0.377) < 1e-9
    # 阈值可配：全部低于阈值时判定通过
    over2, worst2 = aesthetics.count_oriented_overlaps(pairs, max_ratio=0.5)
    assert over2 == 0 and abs(worst2 - 0.377) < 1e-9


def test_evaluate_prefers_rotated_overlap_measurement():
    """页面给出了旋转感知的有向交叠时，不再用轴对齐外接矩形（避免斜排刻度误报）。"""
    measured = _good_measured(
        rects=[_rect(0, 0, 100, 12), _rect(5, 0, 100, 12)],       # 轴对齐会判为交叠
        overlaps=[{"a": "斜排刻度甲", "b": "斜排刻度乙", "ratio": 0.0}],
    )
    report = aesthetics.evaluate(measured, source="query")
    assert report.no_label_overlap and report.max_overlap_ratio == 0.0
    assert not any(i.startswith("label_overlap") for i in report.issues)


def test_evaluate_reports_oriented_overlap_issue():
    measured = _good_measured(overlaps=[{"a": "甲", "b": "乙", "ratio": 0.31}])
    report = aesthetics.evaluate(measured, source="query")
    assert not report.no_label_overlap and not report.passed
    assert report.max_overlap_ratio == 0.31
    assert any(i.startswith("label_overlap") for i in report.issues)


def test_measure_js_keeps_both_overlap_measurements():
    assert "oriented.push" in aesthetics.MEASURE_JS
    assert "overlaps: overlaps.slice" in aesthetics.MEASURE_JS
    assert "getBBox" in aesthetics.MEASURE_JS
    assert "__SEL__" in aesthetics.MEASURE_JS        # 仍由调用方替换容器选择器


def test_evaluate_fully_passing():
    report = aesthetics.evaluate(_good_measured(), source="query")
    assert report.passed and report.issues == []
    assert report.max_overlap_ratio == 0.0


def test_evaluate_flags_overlap_and_truncation():
    measured = _good_measured(
        rects=[_rect(0, 0, 100, 12), _rect(5, 0, 100, 12)],
        truncations=[{"label": ".title", "text": "被裁切", "sw": 300, "cw": 200, "sh": 20, "ch": 20}],
    )
    report = aesthetics.evaluate(measured, source="query")
    assert not report.no_label_overlap and not report.no_text_truncation
    assert not report.passed
    assert any(i.startswith("label_overlap") for i in report.issues)
    assert any(i.startswith("truncation") for i in report.issues)


def test_evaluate_requires_axes_or_titles():
    measured = _good_measured(tickCount={"x": 0, "y": 0}, has_xtitle=False, has_ytitle=False)
    report = aesthetics.evaluate(measured, source="query")
    assert not report.axes_legend_complete


def test_evaluate_multi_trace_requires_legend():
    measured = _good_measured(traceCount=3, legendItems=1)
    report = aesthetics.evaluate(measured, source="query")
    assert not report.axes_legend_complete
    assert any(i.startswith("legend") for i in report.issues)


def test_theme_dark_ok_for_zh_and_light_ok_for_en():
    assert aesthetics.theme_problem("zh", "rgba(0, 0, 0, 0)", "query") is None
    assert aesthetics.theme_problem("en", "#f7f8fb", "query") is None
    assert aesthetics.theme_problem("zh", "#ffffff", "query") is not None
    assert aesthetics.theme_problem(None, "#ffffff", "query") is not None


def test_manual_card_is_light_theme():
    # 手动绘图区是固定浅色卡片，深色模式下也算一致
    assert aesthetics.theme_problem("zh", "#f7f8fb", "manual") is None
    assert aesthetics.theme_problem("zh", "#101010", "manual") is not None


def test_report_serializes_to_schema_shape():
    payload = aesthetics.evaluate(_good_measured(), source="query").to_dict()
    assert set(payload) == {"no_label_overlap", "no_text_truncation", "axes_legend_complete",
                            "theme_consistent", "max_overlap_ratio", "issues"}


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
