"""UI 锚点契约与健康检查（contracts/ui-surface.md §2/§3）。

前端零侵入：全部锚点取自既有实现，不新增 data-testid。
"""
from __future__ import annotations

import re
from pathlib import Path

# id -> (选择器, 硬锚点?, 用途)
ANCHORS: dict[str, tuple[str, bool, str]] = {
    "A1": (".app", True, "主题判定容器（含 data-lang）"),
    "A2": (".lang-btn", False, "语言切换按钮"),
    "A3": (".query-box textarea", True, "提问输入框"),
    "A4": (".query-box button", True, "提交按钮"),
    "A5": (".loading-block", False, "查询进行中提示"),
    "A6": (".result-area", False, "结果区根节点（可含 .manual-open）"),
    "A7": (".result-body", True, "结果容器"),
    "A8": (".msg.error", False, "失败提示"),
    "A9": (".ai-answer", False, "闲聊回答"),
    "A10": (".chart-view", False, "图表区根节点（截图目标，出图后才存在）"),
    "A11": (".chart-view-body", False, "图表主体容器（出图后才存在）"),
    "A12": (".js-plotly-plot", False, "Plotly 根节点（真的画出图形的判据，出图后才存在）"),
    "A13": (".xtick text", False, "x 轴刻度文本（重叠/截断量测）"),
    "A14": (".result-actions", False, "结果区工具条"),
    "A15": (".mode-toggle", True, "手动绘图开关"),
    "A16": (".manual-plot-demo", False, "手动绘图区根节点（打开手动绘图后才存在）"),
}

# 首屏就应存在的硬锚点（doctor 的门禁）
INITIAL_HARD = ("A1", "A3", "A4", "A6", "A7", "A15")
# 只有在「真的画出图表」之后才存在的锚点（probe/build 在首个成功出图后核对）
CHART_HARD = ("A10", "A11", "A12")
# 只有在「打开手动绘图」之后才存在的锚点
MANUAL_HARD = ("A16",)

HARD_ANCHORS = tuple(k for k, (_, hard, _) in ANCHORS.items() if hard)
SOFT_ANCHORS = tuple(k for k, (_, hard, _) in ANCHORS.items() if not hard)


# 渲染/量测时实际使用的选择器
SEL_QUERY_INPUT = ".query-box textarea"
SEL_QUERY_SUBMIT = ".query-box button"
SEL_LOADING = ".loading-block"
SEL_RESULT_BODY = ".result-body"
SEL_ERROR = ".msg.error"
SEL_ERROR_DETAIL = ".msg.error .err-detail"
SEL_ANSWER = ".ai-answer"
SEL_CHART_VIEW = ".chart-view"
SEL_CHART_BODY = ".chart-view-body"
SEL_PLOTLY = ".js-plotly-plot"
SEL_MANUAL_TOGGLE = ".mode-toggle"
SEL_MANUAL_ROOT = ".manual-plot-demo"
SEL_MANUAL_BUILDER = ".chart-builder"
SEL_MANUAL_CHART = ".manual-plot-demo .demo-chart"
SEL_MANUAL_STRIP = ".manual-plot-demo .quality-strip b"
SEL_APP = ".app"

# 「使用 AI 推荐的图表配置」复选框（ChartView 里 recValid 时渲染的唯一复选框）
SEL_AI_REC_TOGGLE = ".chart-view-body input[type=checkbox]"
SEL_CHART_VIEW_BODY_SELECT = ".chart-view-body select"

# 图表类型下拉框：用「选项值包含 Plotly 图型」来定位——
# 通用筛选下拉框的选项是数据列名，不会命中；ChartView.tsx 的 CHART_ORDER 与之保持一致。
CHART_TYPE_SELECT_VALUES = ("bubble", "scatter3d", "heatmap", "parallel", "box", "radar",
                            "line", "bar", "scatter", "pie", "area", "histogram")

# 在页面里定位「图表类型」下拉框（返回页面级下标，-1 表示当前没有该控件）
CHART_TYPE_INDEX_JS = (
    "() => { const vals = " + repr(list(CHART_TYPE_SELECT_VALUES)).replace("'", '"') + ";"
    " const sels = [...document.querySelectorAll('.chart-view-body select')];"
    " return sels.findIndex(s => [...s.options].some(o => vals.includes(o.value))); }"
)

# 与 CHART_TYPE_INDEX_JS 等价的「就绪」判据（供 page.wait_for_function 使用）
CHART_TYPE_READY_JS = (
    "() => { const vals = " + repr(list(CHART_TYPE_SELECT_VALUES)).replace("'", '"') + ";"
    " const sels = [...document.querySelectorAll('.chart-view-body select')];"
    " return sels.some(s => [...s.options].some(o => vals.includes(o.value))); }"
)

# 直接改下拉框取值（原生 setter + change 事件，React 能收到 onChange）。
# 不用 Playwright 的 select_option：它会在页面里打开原生下拉浮层，浮层会残留在底图截图里。
SET_SELECT_VALUE_JS = (
    "([index, value]) => {"
    " const s = document.querySelectorAll('.chart-view-body select')[index];"
    " if (!s) return false;"
    " const setter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set;"
    " setter.call(s, value);"
    " s.dispatchEvent(new Event('change', { bubbles: true }));"
    " return s.value === value; }"
)

# 「图表类型」所在行里各字段下拉框的状态（页面级下标 / 当前值 / 可选项），
# 用于按候选配置截图前手动选定图型字段（横轴、纵轴…）
CHART_TYPE_ROW_STATE_JS = (
    "() => { const vals = " + repr(list(CHART_TYPE_SELECT_VALUES)).replace("'", '"') + ";"
    " const sels = [...document.querySelectorAll('.chart-view-body select')];"
    " const ti = sels.findIndex(s => [...s.options].some(o => vals.includes(o.value)));"
    " if (ti < 0) return [];"
    " const typeSel = sels[ti];"
    " const row = typeSel.closest('.chart-controls') || typeSel.parentElement;"
    " if (!row) return [];"
    " return [...row.querySelectorAll('select')].filter(s => s !== typeSel)"
    "   .map(s => [sels.indexOf(s), s.value, [...s.options].map(o => o.value)]); }"
)

# 手动绘图器（ManualPlotter.tsx）6 个下拉框的固定顺序
MANUAL_SELECT_ORDER = ("chart_type", "x_field", "y_field", "color_field", "size_field", "family")


class UiSurfaceDrift(Exception):
    """硬锚点缺失（退出码 4）。"""

    def __init__(self, missing: list[str]):
        self.missing = missing
        detail = ", ".join(f"{mid}({ANCHORS[mid][0]})" for mid in missing)
        super().__init__(f"界面锚点漂移，以下硬锚点未命中：{detail}")
        self.code = "ui_surface_drift"


def check_selectors(found: dict[str, bool], group: tuple[str, ...] | None = None) -> list[str]:
    """给定「已命中锚点 id 集合」的判定结果，返回缺失的硬锚点 id。"""
    targets = group or INITIAL_HARD
    return [mid for mid in targets if not found.get(mid, False)]


def missing_soft(found: dict[str, bool]) -> list[str]:
    return [mid for mid in SOFT_ANCHORS if not found.get(mid, False)]


def _probe(page, group: tuple[str, ...]) -> tuple[dict[str, bool], list[str]]:
    found: dict[str, bool] = {}
    for mid in group:
        selector = ANCHORS[mid][0]
        try:
            found[mid] = page.query_selector(selector) is not None
        except Exception:                      # noqa: BLE001
            found[mid] = False
    return found, check_selectors(found, group)


def check_page(page) -> tuple[dict[str, bool], list[str]]:
    """首屏锚点核对（doctor）。返回 (命中表, 缺失硬锚点)。"""
    found: dict[str, bool] = {}
    for mid, (selector, _, _) in ANCHORS.items():
        try:
            found[mid] = page.query_selector(selector) is not None
        except Exception:                      # noqa: BLE001
            found[mid] = False
    missing = check_selectors(found, INITIAL_HARD)
    if missing:
        raise UiSurfaceDrift(missing)
    return found, missing


def check_chart(page) -> list[str]:
    """图表锚点核对（probe/build 在首次成功出图后调用）。返回缺失项（空=通过）。"""
    _found, missing = _probe(page, CHART_HARD)
    if missing:
        raise UiSurfaceDrift(missing)
    return missing


def check_manual(page) -> list[str]:
    """手动绘图锚点核对。返回缺失项（空=通过）。"""
    _found, missing = _probe(page, MANUAL_HARD)
    if missing:
        raise UiSurfaceDrift(missing)
    return missing



def doc_anchor_ids(doc_path: Path | None = None) -> dict[str, str]:
    """解析 contracts/ui-surface.md 的锚点表（id -> 选择器），供测试比对。"""
    path = Path(doc_path or Path(__file__).resolve().parents[3]
                / "specs" / "001-intro-video-generator" / "contracts" / "ui-surface.md")
    if not path.is_file():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*(A\d+)\s*\|\s*`([^`]+)`", line)
        if m:
            result[m.group(1)] = m.group(2)
    return result
