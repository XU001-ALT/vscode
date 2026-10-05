"""tools.video.content 单元测试：TOML 读取、跨字段校验与界面锚点契约一致性。

无 pytest 依赖，可直接运行：
    venv\\Scripts\\python.exe tests\\test_video_content.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.video import content as content_mod  # noqa: E402
from tools.video import ui_surface  # noqa: E402

SCENES_TEMPLATE = """
[meta]
version = "1.0.0"
target_duration_sec = [100, 200]
languages = ["zh", "en"]

  [meta.title]
  zh = "示例标题"
  en = "Sample title"

[[shot]]
id = "show_a"
order = 1
kind = "chart_showcase"
source = "cand_a"
zoom = "in"
  [shot.title]
  zh = "图表甲"
  en = "Chart A"
  [shot.narration]
  zh = "这是第一段旁白，用来演示平台如何把一句自然语言问题变成一张可以直接汇报的图表。"
  en = "This is the first narration, used to show how a plain question becomes a chart ready to present."

[[shot]]
id = "show_b"
order = 2
kind = "chart_showcase"
source = "cand_b"
  [shot.title]
  zh = "图表乙"
  en = "Chart B"
  [shot.narration]
  zh = "这是第二段旁白，换一个维度继续对比实验数据，让趋势与差异都能被清楚地看到。"
  en = "This is the second narration, comparing another dimension so trends and gaps stay visible."

[[shot]]
id = "show_c"
order = 3
kind = "chart_showcase"
source = "cand_c"
  [shot.title]
  zh = "图表丙"
  en = "Chart C"
  [shot.narration]
  zh = "这是第三段旁白，用于凑满三个问答出图样例，满足内容定义的硬性数量要求。"
  en = "This is the third narration, filling the three question-answer samples required by the content rules."

[[shot]]
id = "show_manual"
order = 4
kind = "manual_plot"
source = "manual_a"
  [shot.title]
  zh = "手动绘图"
  en = "Manual chart"
  [shot.narration]
  zh = "这是手动绘图样例，说明除了自动出图之外，也可以自己选择图型与字段来组织画面。"
  en = "This is the manual chart sample, showing that chart type and fields can also be chosen by hand."

[[shot]]
id = "bilingual"
order = 5
kind = "bilingual_demo"
  [shot.title]
  zh = "语言切换"
  en = "Language switch"
  [shot.narration]
  zh = "这是语言切换样例，演示同一套数据可以分别用中文与英文界面展示给不同地区的同事。"
  en = "This is the language switch sample, showing one data set presented in two different languages."

[[shot]]
id = "explain"
order = 6
kind = "ui_explain"
  [shot.title]
  zh = "界面说明"
  en = "Interface tour"
  [shot.narration]
  zh = "这是界面说明样例，用来介绍图表以外的配置区、工具条与结果区各自负责什么。"
  en = "This is the interface tour, explaining the configuration panel, toolbar and result area."
"""

CANDIDATES_TEMPLATE = """
[meta]
version = "1.0.0"

[[candidate]]
id = "cand_a"
  [candidate.prompt]
  zh = "对比全部测试的压力与容量分布"
  en = "Compare pressure against capacity across all tests"

[[candidate]]
id = "cand_b"
  [candidate.prompt]
  zh = "对比不同温度下的容量变化"
  en = "Compare capacity changes at different temperatures"

[[candidate]]
id = "cand_c"
  [candidate.prompt]
  zh = "按年份对比文献数量"
  en = "Compare the number of papers by year"

[[candidate]]
id = "cand_d"
  [candidate.prompt]
  zh = "对比各类实验的活化能差异"
  en = "Compare activation energy differences across experiments"

[[candidate]]
id = "cand_e"
  [candidate.prompt]
  zh = "对比各循环测试的圈数分布"
  en = "Compare the loop count distribution across cycling tests"

[[candidate]]
id = "cand_f"
  [candidate.prompt]
  zh = "对比各测试的起始温度分布"
  en = "Compare the onset temperature distribution across tests"

[[candidate]]
id = "cand_g"
  [candidate.prompt]
  zh = "对比各改性实验的添加量"
  en = "Compare the additive amount across modification experiments"

[[candidate]]
id = "cand_h"
  [candidate.prompt]
  zh = "对比各等温测试的压力与活化能"
  en = "Compare pressure against activation energy for isothermal tests"

[[manual]]
id = "manual_a"
chart_type = "bubble"
x_field = "desorptionTemp"
y_fields = ["capacity"]
color_field = "year"
size_field = "retention"
  [manual.title]
  zh = "温度与容量气泡图"
  en = "Temperature vs capacity bubble chart"
"""


def _write(tmp: Path, scenes: str = SCENES_TEMPLATE,
           candidates: str = CANDIDATES_TEMPLATE) -> Path:
    (tmp / "scenes.toml").write_text(scenes, encoding="utf-8")
    (tmp / "candidates.toml").write_text(candidates, encoding="utf-8")
    return tmp


def _expect_error(scenes: str | None = None, candidates: str | None = None) -> str:
    with tempfile.TemporaryDirectory() as raw:
        tmp = _write(Path(raw), scenes or SCENES_TEMPLATE, candidates or CANDIDATES_TEMPLATE)
        try:
            content_mod.load_content(tmp)
        except content_mod.ContentError as exc:
            return exc.code
        raise AssertionError("应当抛出 ContentError")


def test_load_valid_content():
    with tempfile.TemporaryDirectory() as raw:
        loaded = content_mod.load_content(_write(Path(raw)))
    assert len(loaded.shots) == 6 and len(loaded.candidates) == 8 and len(loaded.manuals) == 1
    assert loaded.short_sha and len(loaded.short_sha) == 7
    assert loaded.version_label == "scenes=1.0.0,candidates=1.0.0"


def test_real_content_definition_is_valid():
    loaded = content_mod.load_content()
    assert len(loaded.shots) >= 8
    kinds = [s.kind for s in loaded.shots]
    assert kinds.count("chart_showcase") >= 3
    assert kinds.count("manual_plot") >= 1
    assert kinds.count("bilingual_demo") == 1
    assert kinds.count("ui_explain") >= 1
    assert [s.order for s in loaded.shots] == list(range(1, len(loaded.shots) + 1))


def test_order_must_be_contiguous():
    broken = SCENES_TEMPLATE.replace("order = 3", "order = 9")
    assert _expect_error(scenes=broken) == "order_not_contiguous"


def test_missing_language_text_rejected():
    broken = SCENES_TEMPLATE.replace('  en = "Sample title"\n', "")
    assert _expect_error(scenes=broken) == "content_invalid"


def test_english_word_in_chinese_text_rejected():
    broken = SCENES_TEMPLATE.replace('zh = "示例标题"', 'zh = "Sample 标题"')
    assert _expect_error(scenes=broken) == "content_invalid"


def test_chinese_char_in_english_text_rejected():
    broken = SCENES_TEMPLATE.replace('en = "Sample title"', 'en = "标题 title"')
    assert _expect_error(scenes=broken) == "content_invalid"


def test_unknown_source_rejected():
    broken = SCENES_TEMPLATE.replace('source = "cand_c"', 'source = "nope"')
    assert _expect_error(scenes=broken) == "source_not_found"


def test_source_forbidden_on_other_kinds():
    broken = SCENES_TEMPLATE.replace('kind = "ui_explain"\n', 'kind = "ui_explain"\nsource = "cand_a"\n')
    assert _expect_error(scenes=broken) == "content_invalid"


def test_manual_field_must_exist_in_plotter():
    broken = CANDIDATES_TEMPLATE.replace('x_field = "desorptionTemp"', 'x_field = "not_a_field"')
    assert _expect_error(candidates=broken) == "field_not_found"


def test_bubble_requires_size_and_color():
    broken = CANDIDATES_TEMPLATE.replace('size_field = "retention"\n', "")
    assert _expect_error(candidates=broken) == "content_invalid"


def test_too_few_candidates_rejected():
    start = CANDIDATES_TEMPLATE.index('[[candidate]]\nid = "cand_e"')
    end = CANDIDATES_TEMPLATE.index("[[manual]]")
    trimmed = CANDIDATES_TEMPLATE[:start] + CANDIDATES_TEMPLATE[end:]
    assert _expect_error(candidates=trimmed) == "content_invalid"


def test_manual_chart_selection_fields_are_parsed():
    patched = CANDIDATES_TEMPLATE.replace(
        'id = "cand_a"\n',
        'id = "cand_a"\nai_recommend = false\nchart_type = "bar"\nfields = ["year", "count"]\n')
    with tempfile.TemporaryDirectory() as raw:
        loaded = content_mod.load_content(_write(Path(raw), candidates=patched))
    cand = loaded.candidates[0]
    assert cand.ai_recommend is False
    assert cand.chart_type == "bar"
    assert cand.fields == ("year", "count")
    # 其余候选保持默认：走 AI 推荐、不手动选型
    assert loaded.candidates[1].ai_recommend is True
    assert loaded.candidates[1].chart_type is None and loaded.candidates[1].fields == ()


def test_chart_type_without_disabling_ai_recommend_rejected():
    broken = CANDIDATES_TEMPLATE.replace('id = "cand_a"\n', 'id = "cand_a"\nchart_type = "bar"\n')
    assert _expect_error(candidates=broken) == "content_invalid"


def test_fields_without_disabling_ai_recommend_rejected():
    broken = CANDIDATES_TEMPLATE.replace('id = "cand_a"\n',
                                         'id = "cand_a"\nfields = ["year"]\n')
    assert _expect_error(candidates=broken) == "content_invalid"


def test_unknown_chart_type_rejected():
    broken = CANDIDATES_TEMPLATE.replace(
        'id = "cand_a"\n', 'id = "cand_a"\nai_recommend = false\nchart_type = "sankey"\n')
    assert _expect_error(candidates=broken) == "content_invalid"


def test_non_string_fields_rejected():
    broken = CANDIDATES_TEMPLATE.replace(
        'id = "cand_a"\n', 'id = "cand_a"\nai_recommend = false\nfields = [1, 2]\n')
    assert _expect_error(candidates=broken) == "content_invalid"


def test_real_candidates_declare_manual_selection_candidate():
    loaded = content_mod.load_content()
    manual_choice = [c for c in loaded.candidates if not c.ai_recommend]
    assert manual_choice, "内容里应至少有一条「关闭 AI 推荐 + 手动选型」的候选"
    assert all(c.chart_type for c in manual_choice)


def test_duration_out_of_range():
    broken = SCENES_TEMPLATE.replace('id = "show_a"\norder = 1\n', 'id = "show_a"\norder = 1\nduration_sec = 99.0\n')
    assert _expect_error(scenes=broken) == "duration_out_of_range"


def test_localize_projection():
    text = content_mod.LocalizedText(zh="中文", en="English")
    assert content_mod.localize(text, "zh") == "中文"
    assert content_mod.localize(text, "en") == "English"


def test_shot_text_for_is_already_localized_text():
    """Shot.text_for 直接返回该语言的旁白文本（build 侧不能再套一层 localize）。"""
    loaded = content_mod.load_content()
    shot = loaded.shots[0]
    zh, en = shot.text_for("zh"), shot.text_for("en")
    assert isinstance(zh, str) and isinstance(en, str)
    assert zh and en and zh != en


def test_ui_surface_anchors_match_contract_doc():
    documented = ui_surface.doc_anchor_ids()
    assert documented, "契约文档 contracts/ui-surface.md 未解析到锚点表"
    assert set(documented) == set(ui_surface.ANCHORS), "锚点 id 集合与契约不一致"


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

