"""tools.video.capture 单元测试：16:9 取景框计算（纯函数，不需要浏览器）。

无 pytest 依赖，可直接运行：
    venv\\Scripts\\python.exe tests\\test_video_capture.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.video import capture  # noqa: E402

VIEWPORT = {"width": 1600, "height": 950}


def test_chart_box_is_widened_to_16x9_without_losing_content():
    box = {"x": 662.0, "y": 281.0, "width": 590.0, "height": 646.0}
    clip = capture.clip_16x9(box, VIEWPORT)
    assert abs(clip["width"] / clip["height"] - 16 / 9) < 0.01
    assert clip["height"] == 646.0                     # 高度不裁，内容全在
    assert clip["x"] <= box["x"]
    assert clip["x"] + clip["width"] >= box["x"] + box["width"]
    assert clip["y"] == box["y"]


def test_wide_box_is_not_shrunk():
    box = {"x": 100.0, "y": 100.0, "width": 1400.0, "height": 600.0}
    clip = capture.clip_16x9(box, VIEWPORT)
    assert clip["width"] == 1400.0 and clip["height"] == 600.0
    assert clip["x"] == 100.0 and clip["y"] == 100.0


def test_clip_is_clamped_into_viewport():
    box = {"x": 20.0, "y": 5.0, "width": 590.0, "height": 940.0}
    clip = capture.clip_16x9(box, VIEWPORT)
    assert clip["x"] >= 0 and clip["x"] + clip["width"] <= VIEWPORT["width"] + 0.01
    assert clip["y"] >= 0 and clip["y"] + clip["height"] <= VIEWPORT["height"] + 0.01
    assert clip["height"] == 940.0


def test_degenerate_box_is_returned_unchanged():
    box = {"x": 1.0, "y": 2.0, "width": 0.0, "height": 0.0}
    assert capture.clip_16x9(box, VIEWPORT) == box


def test_ratio_is_configurable():
    box = {"x": 0.0, "y": 0.0, "width": 400.0, "height": 400.0}
    clip = capture.clip_16x9(box, VIEWPORT, ratio=1.0)
    assert clip["width"] == 400.0 and clip["height"] == 400.0


def test_match_field_prefers_exact_then_substring():
    options = ["year", "paper_count", "sample_id"]
    assert capture.match_field(options, "year") == "year"
    # 列名随后端 SQL 别名变化：写 count 也能命中 paper_count
    assert capture.match_field(options, "count") == "paper_count"
    assert capture.match_field(options, "PAPER") == "paper_count"
    assert capture.match_field(options, "missing") is None


def test_match_field_skips_values_already_used():
    options = ["year", "paper_count"]
    assert capture.match_field(options, "year", used=["year"]) is None
    assert capture.match_field(options, "count", used=["year"]) == "paper_count"
    assert capture.match_field(options, "count", used=["paper_count"]) is None


def test_match_field_ignores_blank_query():
    assert capture.match_field(["year"], "") is None
    assert capture.match_field([], "year") is None


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
