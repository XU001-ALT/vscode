"""驱动真实界面采集（FR-002 / FR-003）。

用 Playwright 驱动系统 Edge/Chrome（无需 `playwright install`）：
聚焦提问框 → 逐字输入 → 提交 → 等待图表渲染或报错 → 元素级高清截图（plate）。
可选录制 viewport 视频（clip），默认关闭以加快探测。
"""
from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Sequence

from . import aesthetics, safety, settings as S
from . import ui_surface as U

try:  # 未安装 playwright 时仍可 import（离线单测只用到纯函数）
    from playwright.sync_api import sync_playwright
except Exception:  # noqa: BLE001
    sync_playwright = None


class CaptureError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


@dataclass
class CaptureSnapshot:
    has_plotly: bool = False
    traces: list[dict] = field(default_factory=list)
    error_text: str = ""
    answer_text: str = ""
    record_count: int | None = None
    plate: str | None = None
    clip: str | None = None
    aesthetics: dict | None = None
    elapsed_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@contextmanager
def browser_session(*, headed: bool = False, channel: str | None = None,
                    record_video_dir: Path | None = None, base_url: str | None = None,
                    device_scale: int | None = None):
    """打开浏览器与上下文；channel 为空时按 msedge → chrome → 默认 顺序回退。"""
    if sync_playwright is None:
        raise CaptureError("playwright_missing",
                           "未安装 playwright：请在 chat-data-assistant 下执行 "
                           "`venv\\Scripts\\python.exe -m pip install -r tools/video/requirements-video.txt`")
    channels = [channel] if channel else list(S.BROWSER_CHANNELS)
    last_error: Exception | None = None
    with sync_playwright() as pw:
        for ch in channels:
            try:
                browser = pw.chromium.launch(channel=ch, headless=not headed)
            except Exception as exc:  # noqa: BLE001 - 逐个通道尝试
                last_error = exc
                continue
            kwargs = {
                "viewport": dict(S.VIEWPORT),
                "device_scale_factor": device_scale or S.DEVICE_SCALE_FACTOR,
                "locale": "zh-CN",
                "ignore_https_errors": True,
            }
            if record_video_dir:
                Path(record_video_dir).mkdir(parents=True, exist_ok=True)
                kwargs["record_video_dir"] = str(record_video_dir)
            context = browser.new_context(**kwargs)
            try:
                yield browser, context, context.new_page()
            finally:
                try:
                    context.close()
                finally:
                    browser.close()
            return
        raise CaptureError("browser_launch_failed",
                           f"无法启动系统浏览器通道 {channels}：{last_error}")


def open_app(page, *, base_url: str | None = None, timeout: int = 60_000) -> None:
    url = (base_url or S.FRONTEND_URL).rstrip("/") + "/"
    page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    page.wait_for_selector(U.SEL_APP, timeout=timeout)
    page.wait_for_selector(U.SEL_QUERY_INPUT, timeout=timeout)


def current_lang(page) -> str | None:
    return page.evaluate(
        "() => { const a = document.querySelector('.app'); return a ? a.getAttribute('data-lang') : null; }"
    )


def ensure_lang(page, lang: str, *, timeout: int = 20_000) -> bool:
    """切换界面语言；返回是否发生了切换（FR-012 的展示动作）。"""
    if current_lang(page) == lang:
        return False
    page.click(U.SEL_APP + " .lang-btn")
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        if current_lang(page) == lang:
            return True
        page.wait_for_timeout(150)
    raise CaptureError("lang_switch_failed", f"界面语言未能切换到 {lang}")


def _read_result(page, container: str) -> dict:
    """读取结果区证据（图表轨迹 / 错误 / 回答）。"""
    payload = page.evaluate(
        aesthetics.MEASURE_JS.replace("__SEL__", json.dumps(container))
    ) if page.query_selector(container) else None
    error_text = ""
    if page.query_selector(U.SEL_ERROR):
        error_text = page.eval_on_selector(
            U.SEL_ERROR, "el => (el.textContent || '').trim()"
        ) or ""
    answer_text = ""
    if page.query_selector(U.SEL_ANSWER):
        answer_text = page.eval_on_selector(
            U.SEL_ANSWER, "el => (el.textContent || '').trim()"
        ) or ""
    record_count = None
    if page.query_selector(U.SEL_MANUAL_STRIP):
        raw = page.eval_on_selector(U.SEL_MANUAL_STRIP, "el => (el.textContent || '').trim()") or ""
        digits = "".join(ch for ch in raw.split(" ")[0] if ch.isdigit())
        record_count = int(digits) if digits else None
    return {
        "measure": payload,
        "error_text": safety.sanitize(error_text)[:400],
        "answer_text": safety.sanitize(answer_text)[:400],
        "record_count": record_count,
    }


def _snapshot_from(evidence: dict, *, plate: str | None, clip: str | None,
                   started: float, source: str) -> CaptureSnapshot:
    measure = evidence.get("measure") or {}
    if measure:
        report = measure.get("report") or aesthetics.evaluate(measure, source).to_dict()
    else:
        report = aesthetics.AestheticsReport(False, False, False, False, 1.0,
                                             ["container_missing"]).to_dict()
    return CaptureSnapshot(
        has_plotly=bool(measure.get("found")),
        traces=list(measure.get("traces") or []),
        error_text=evidence.get("error_text") or "",
        answer_text=evidence.get("answer_text") or "",
        record_count=evidence.get("record_count"),
        plate=plate,
        clip=clip,
        aesthetics=report,
        elapsed_ms=int((time.time() - started) * 1000),
    )


def clip_16x9(box: dict, viewport: dict, ratio: float = 16 / 9) -> dict:
    """把元素盒扩成 ``ratio``（默认 16:9）的取景框：横向加宽、高度不动，并夹在视口内。

    成片画布是 16:9，而界面元素（``.chart-view`` / ``.manual-plot-demo``）是竖长比例；
    以 16:9 取景可以既保住元素完整（高度完全覆盖），又把周边界面一并入画，
    避免成片里出现大片空边或把图裁掉（用户实测反馈：截图比例不对 / 像是没截全）。
    """
    x, y = float(box.get("x", 0.0)), float(box.get("y", 0.0))
    width, height = float(box.get("width", 0.0)), float(box.get("height", 0.0))
    view_w, view_h = float(viewport.get("width", 0.0)), float(viewport.get("height", 0.0))
    if height <= 0 or width <= 0:
        return {"x": round(x, 2), "y": round(y, 2), "width": round(width, 2), "height": round(height, 2)}
    height = min(height, view_h) if view_h else height
    width = max(width, height * ratio)
    if view_w:
        width = min(width, view_w)
        x = min(max(0.0, x - (width - box["width"]) / 2), view_w - width)
    if view_h:
        y = min(max(0.0, y), view_h - height)
    return {"x": round(x, 2), "y": round(y, 2), "width": round(width, 2), "height": round(height, 2)}


def _element_box(page, selector: str) -> dict | None:
    return page.evaluate(
        """(sel) => { const el = document.querySelector(sel); if (!el) return null;
             const r = el.getBoundingClientRect();
             return { x: r.x, y: r.y, width: r.width, height: r.height,
                      viewport: { width: window.innerWidth, height: window.innerHeight } }; }""",
        selector,
    )


def screenshot_plate(page, selector: str, target: Path) -> str | None:
    """采集底图：优先按 16:9 取景（含周边界面），失败则退回元素级截图。"""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    box = _element_box(page, selector)
    if box:
        clip = clip_16x9(box, box.pop("viewport") or {})
        try:
            page.screenshot(path=str(target), clip=clip)
            return str(target)
        except Exception:                      # noqa: BLE001 - 取景失败时退回元素截图
            pass
    try:
        page.locator(selector).screenshot(path=str(target))
        return str(target)
    except Exception:                          # noqa: BLE001 - 截图失败不应判为「没出图」
        return None


def match_field(options: Sequence[str], wanted: str, used: Sequence[str] = ()) -> str | None:
    """在字段下拉框的可选项里匹配候选配置的字段名（列名由后端 SQL 别名决定，故放宽匹配）。

    依次尝试：忽略大小写的全等 → 忽略大小写的包含（如 ``count`` 命中 ``paper_count``）；
    已占用的值不再选中，返回应选中的选项值，全部不命中时返回 ``None``。
    """
    key = str(wanted).strip().lower()
    if not key:
        return None
    taken = {str(v).strip().lower() for v in used}
    candidates = [o for o in options if str(o).strip().lower() not in taken]
    for value in candidates:
        if str(value).strip().lower() == key:
            return value
    for value in candidates:
        if key in str(value).strip().lower():
            return value
    return None


def _chart_type_row(page) -> list[dict]:
    """读取「图表类型」行里各字段下拉框的状态（下标 / 当前值 / 可选项）。"""
    rows = page.evaluate(U.CHART_TYPE_ROW_STATE_JS) or []
    return [{"index": int(r[0]), "value": str(r[1]), "options": [str(o) for o in r[2]]}
            for r in rows]


def _set_select_value(page, index: int, value: str) -> bool:
    """在不打开原生下拉浮层的前提下改下拉框取值（浮层会残留在底图里）。"""
    try:
        return bool(page.evaluate(U.SET_SELECT_VALUE_JS, [index, value]))
    except Exception:                          # noqa: BLE001 - 失败时退回 Playwright 的选值
        return False


def _chart_controls_touched(page, *, ai_recommend: bool, chart_type: str | None,
                            fields: Sequence[str], timeout_ms: int) -> float:
    """在结果区里操作「AI 推荐」开关与手动选型，返回等待重绘的毫秒数（0=没动手）。"""
    waited = 0
    toggle = page.locator(U.SEL_AI_REC_TOGGLE)
    if toggle.count():
        try:
            if not ai_recommend and toggle.first.is_checked():
                toggle.first.uncheck()
                page.wait_for_timeout(250)
                waited += 250
        except Exception:                      # noqa: BLE001 - 控件被重绘时忽略
            pass
    if not chart_type and not fields:
        return waited
    try:
        page.wait_for_function(U.CHART_TYPE_READY_JS, timeout=timeout_ms)
    except Exception:                          # noqa: BLE001 - 后端没给推荐时没有手动选型控件
        return waited
    selects = page.locator(U.SEL_CHART_VIEW_BODY_SELECT)

    def choose(index: int, value: str) -> None:
        if not _set_select_value(page, index, value):
            selects.nth(index).select_option(value)
        page.wait_for_timeout(300)

    if chart_type:
        index = int(page.evaluate(U.CHART_TYPE_INDEX_JS))
        if index >= 0:
            choose(index, chart_type)
            page.wait_for_timeout(150)
            waited += 450

    # 字段按「图表类型行里的顺序」依次对应（横轴 → 纵轴 → …），列名做放宽匹配
    used: list[str] = []
    for wanted, slot in zip(fields, _chart_type_row(page)):
        hit = match_field(slot["options"], wanted, used)
        if hit and hit != slot["value"]:
            choose(slot["index"], hit)
            waited += 300
        if hit:
            used.append(hit)

    # 双轴型兜底：默认横纵轴都指向第一个数值列，取值相同时图会退化成一条无意义的直线
    row = _chart_type_row(page)
    if len(row) >= 2 and row[0]["value"] and row[0]["value"] == row[1]["value"]:
        alt = next((o for o in row[1]["options"] if o != row[0]["value"]), None)
        if alt:
            choose(row[1]["index"], alt)
            waited += 300
    if waited:
        try:                                   # 收尾：撤掉焦点环，避免底图出现输入态
            page.evaluate("() => { const el = document.activeElement;"
                          " if (el && el.blur) el.blur(); }")
        except Exception:                      # noqa: BLE001 - 属增强项
            pass
    return waited


def ask_query(page, question: str, *, out_dir: Path, plate_name: str,
              timeout_ms: int | None = None, lang: str = "zh",
              with_clips: bool = False, clip_dir: Path | None = None,
              ai_recommend: bool = True, chart_type: str | None = None,
              fields: Sequence[str] = ()) -> CaptureSnapshot:
    """执行一次真实提问并采集证据；每次重新加载页面以消除上一次结果的残留。

    ``ai_recommend=False`` 会取消勾选界面里的「使用 AI 推荐的图表配置」，
    ``chart_type`` / ``fields`` 则在该状态下手动指定图型与字段（内容侧可编辑，FR-016）。
    """
    started = time.time()
    limit = timeout_ms or S.PER_QUERY_TIMEOUT_MS
    open_app(page)
    ensure_lang(page, lang)

    page.wait_for_selector(U.SEL_QUERY_INPUT, timeout=30_000)
    textarea = page.locator(U.SEL_QUERY_INPUT)
    textarea.click()
    textarea.fill("")
    textarea.type(question, delay=12)          # 逐字输入：保留真实交互画面
    page.click(U.SEL_QUERY_SUBMIT)

    # 等「查询中」出现再消失，作为本次查询的确定性边界
    try:
        page.wait_for_selector(U.SEL_LOADING, timeout=8_000, state="visible")
    except Exception:  # noqa: BLE001 - 极快的结果可能来不及出现 loading
        pass
    try:
        page.wait_for_selector(U.SEL_LOADING, timeout=limit, state="hidden")
    except Exception:  # noqa: BLE001
        pass

    # 等结果区出现（图表 / 报错 / 回答三选一）
    try:
        page.wait_for_function(
            """() => document.querySelector('.js-plotly-plot')
                     || document.querySelector('.msg.error')
                     || document.querySelector('.ai-answer')""",
            timeout=limit,
        )
    except Exception:  # noqa: BLE001
        pass
    page.wait_for_timeout(600)                 # 让 Plotly 的入场动画稳定下来

    # 关闭 AI 推荐 / 手动指定图型与字段（内容侧可编辑的人工干预入口，FR-016）
    if not ai_recommend or chart_type or fields:
        if _chart_controls_touched(page, ai_recommend=ai_recommend, chart_type=chart_type,
                                   fields=fields, timeout_ms=limit):
            page.wait_for_timeout(400)         # 等 React 重渲染 + Plotly 重绘

    evidence = _read_result(page, U.SEL_CHART_VIEW)
    plate = None
    if evidence["measure"]:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        plate = screenshot_plate(page, U.SEL_CHART_VIEW, out_dir / plate_name)

    clip = None
    if with_clips and clip_dir is not None:
        clip = _save_clip(page, Path(clip_dir) / f"{Path(plate_name).stem}.webm")
    return _snapshot_from(evidence, plate=plate, clip=clip, started=started, source="query")


def _save_clip(page, target: Path) -> str | None:
    """把 Playwright 录制的 viewport 视频留存到目标路径（尽力而为）。"""
    try:
        video = page.video
        if video is None:
            return None
        src = Path(video.path())
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.resolve() != target.resolve():
            target.write_bytes(src.read_bytes())
        return str(target)
    except Exception:  # noqa: BLE001 - 录屏属增强项，失败不影响探测
        return None


def capture_manual(page, manual, *, out_dir: Path, plate_name: str,
                   timeout_ms: int | None = None, lang: str = "zh") -> CaptureSnapshot:
    """切换手动绘图模式并按内容定义设置图型/字段，采集成品图（FR-011）。"""
    started = time.time()
    limit = timeout_ms or S.PER_QUERY_TIMEOUT_MS
    open_app(page)
    ensure_lang(page, lang)

    page.click(U.SEL_MANUAL_TOGGLE)
    page.wait_for_selector(U.SEL_MANUAL_ROOT, timeout=30_000)
    count = page.locator(f"{U.SEL_MANUAL_BUILDER} select").count()
    if count < 2:
        raise CaptureError("manual_controls_missing", "手动绘图控件未找到（.chart-builder select）")

    # 下拉框顺序：chart_type / x_field / y_field / color_field / size_field / family
    values = [manual.chart_type, manual.x_field,
              (manual.y_fields or (None,))[0], manual.color_field, manual.size_field]
    for index, value in enumerate(values):
        if value is None or index >= count:
            continue
        page.locator(f"{U.SEL_MANUAL_BUILDER} select").nth(index).select_option(str(value))
        page.wait_for_timeout(280)             # 触发表重新渲染

    page.wait_for_selector(U.SEL_MANUAL_CHART, timeout=limit)
    try:
        # Plotly 会把 js-plotly-plot 直接加在 .demo-chart 容器上（不是子节点）
        page.wait_for_function(
            "() => { const c = document.querySelector('.manual-plot-demo .demo-chart');"
            " return !!(c && (c.classList.contains('js-plotly-plot')"
            " || c.querySelector('.js-plotly-plot'))); }",
            timeout=min(limit, 30_000),
        )
    except Exception:  # noqa: BLE001
        pass
    page.wait_for_timeout(800)

    evidence = _read_result(page, U.SEL_MANUAL_ROOT)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    plate = screenshot_plate(page, U.SEL_MANUAL_ROOT, out_dir / plate_name)
    return _snapshot_from(evidence, plate=plate, clip=None, started=started, source="manual")


def capture_page_plate(page, *, out_dir: Path, name: str, lang: str = "zh",
                       toggle_lang: bool = False, question: str | None = None) -> str:
    """整页截图（ui_explain / bilingual_demo / outro 的背景底图，FR-012 / FR-015）。

    若给出 ``question``，先跑一次真实提问，让整页画面里带上图表结果，
    这样「以图表画面为背景」在整page层面同样成立。
    """
    open_app(page)
    ensure_lang(page, lang)
    if question:
        try:
            ask_query(page, question, out_dir=out_dir, plate_name=".page-tmp.png", lang=lang)
        except Exception:                   # noqa: BLE001 - 底图不因提问失败而中断
            pass
        page.wait_for_timeout(400)
    if toggle_lang:
        page.click(U.SEL_APP + " .lang-btn")
        page.wait_for_timeout(900)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / name
    page.screenshot(path=str(target))
    tmp = Path(out_dir) / ".page-tmp.png"
    if tmp.is_file():
        tmp.unlink()
    return str(target)



