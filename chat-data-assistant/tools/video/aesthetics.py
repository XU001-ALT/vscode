"""排版美观判定（FR-009）：确定性几何量测，纯函数可离线单测。"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from . import settings as S

# 深色主题（data-lang=zh）与浅色主题下可接受的 Plotly 背景值
_DARK_BG = {"rgba(0, 0, 0, 0)", "rgba(20,30,60,0.45)", "transparent"}
_LIGHT_BG = {"rgba(0, 0, 0, 0)", "#f7f8fb", "rgb(247, 248, 251)", "rgba(255, 255, 255, 0)", "white"}


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float
    kind: str = ""
    text: str = ""

    @property
    def area(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)

    def intersects(self, other: "Rect") -> bool:
        return not (self.x + self.width <= other.x or other.x + other.width <= self.x
                    or self.y + self.height <= other.y or other.y + other.height <= self.y)


@dataclass
class AestheticsReport:
    no_label_overlap: bool
    no_text_truncation: bool
    axes_legend_complete: bool
    theme_consistent: bool
    max_overlap_ratio: float
    issues: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (self.no_label_overlap and self.no_text_truncation
                and self.axes_legend_complete and self.theme_consistent)

    def to_dict(self) -> dict:
        return asdict(self)


def to_rects(items: list[dict]) -> list[Rect]:
    return [Rect(float(i.get("x", 0)), float(i.get("y", 0)), float(i.get("width", 0)),
                 float(i.get("height", 0)), str(i.get("kind", "")), str(i.get("text", "")))
            for i in items]


def overlap_ratio(a: Rect, b: Rect) -> float:
    """交叠面积 / 较小面积；不交叠返回 0。"""
    if not a.intersects(b):
        return 0.0
    ox = min(a.x + a.width, b.x + b.width) - max(a.x, b.x)
    oy = min(a.y + a.height, b.y + b.height) - max(a.y, b.y)
    inter = max(0.0, ox) * max(0.0, oy)
    smaller = min(a.area, b.area)
    if smaller <= 0:
        return 0.0
    return inter / smaller


def count_overlaps(rects: list[Rect], max_ratio: float = S.MAX_OVERLAP_RATIO) -> tuple[int, float]:
    """返回（达到/超过阈值的文本对数, 实测最大交叠比）。"""
    worst = 0.0
    over = 0
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            ratio = overlap_ratio(rects[i], rects[j])
            worst = max(worst, ratio)
            if ratio >= max_ratio:
                over += 1
    return over, round(worst, 4)


def count_oriented_overlaps(pairs: list[dict],
                            max_ratio: float = S.MAX_OVERLAP_RATIO) -> tuple[int, float]:
    """旋转感知的标签交叠判定：``pairs`` 由页面内量测脚本给出。

    页面侧把文字还原成「中心 + 自身宽高 + 旋转角」的有向矩形，用凸多边形裁剪求真实交集比；
    轴对齐外接矩形会把斜排刻度（Plotly ``tickangle``）判成交叠（实测误报 37.7%），
    故交叠只在页面里算，Python 侧只负责阈值判定，保持阈值可配置。
    """
    worst = 0.0
    over = 0
    for item in pairs:
        ratio = float(item.get("ratio") or 0.0)
        worst = max(worst, ratio)
        if ratio >= max_ratio:
            over += 1
    return over, round(worst, 4)


def find_truncations(items: list[dict]) -> list[str]:
    """文本溢出检测：scrollWidth/clientWidth 与 scrollHeight/clientHeight 双向比较。"""
    issues: list[str] = []
    for item in items:
        sw, cw = float(item.get("sw", 0)), float(item.get("cw", 0))
        sh, ch = float(item.get("sh", 0)), float(item.get("ch", 0))
        if cw > 0 and sw > cw + 1:
            issues.append(f"truncation:{item.get('label', '?')}:{item.get('text', '')[:16]}(横向 {sw:.0f}>{cw:.0f})")
        if ch > 0 and sh > ch + 1:
            issues.append(f"truncation:{item.get('label', '?')}:{item.get('text', '')[:16]}(纵向 {sh:.0f}>{ch:.0f})")
    return issues


def theme_problem(app_lang: str | None, paper_bgcolor: str | None, source: str) -> str | None:
    """配色与界面主题一致性：返回问题描述或 None。"""
    if app_lang not in S.LANGUAGES:
        return "theme:未能读取 .app[data-lang]"
    bg = (paper_bgcolor or "").strip().lower().replace(" ", "")
    if source == "manual":
        # 手动绘图区是固定浅色卡片（设计如此），与深蓝主题形成对比
        accepted = {b.replace(" ", "") for b in _LIGHT_BG}
    elif app_lang == "zh":
        accepted = {b.replace(" ", "") for b in _DARK_BG}
    else:
        accepted = {b.replace(" ", "") for b in _LIGHT_BG}
    if bg in accepted:
        return None
    return f"theme:Plotly 背景 {paper_bgcolor!r} 与 data-lang={app_lang} 的期望不一致"


def evaluate(measured: dict, source: str) -> AestheticsReport:
    """由量测原始数据得出四项判定与 issues。"""
    issues: list[str] = []
    rects = to_rects(measured.get("rects") or [])
    if measured.get("overlaps") is not None:
        over_pairs, worst = count_oriented_overlaps(measured["overlaps"])
    else:                                   # 旧量测载荷 / 单测夹具：退回轴对齐矩形
        over_pairs, worst = count_overlaps(rects)
    if over_pairs:
        issues.append(f"label_overlap:{over_pairs} 对文本交叠（最大 {worst:.2%}）")

    truncations = find_truncations(measured.get("truncations") or [])
    issues.extend(truncations)

    ticks = measured.get("tickCount") or {}
    legend_items = int(measured.get("legendItems") or 0)
    trace_count = int(measured.get("traceCount") or 1)
    has_xt = bool(measured.get("has_xtitle"))
    has_yt = bool(measured.get("has_ytitle"))
    axes_ok = ((int(ticks.get("x", 0)) >= S.MIN_TICK_COUNT and int(ticks.get("y", 0)) >= S.MIN_TICK_COUNT)
               or (has_xt and has_yt))
    legend_ok = legend_items >= 2 or trace_count <= 1
    if not axes_ok:
        issues.append(f"axes:{ticks} 刻度不足且缺少轴标题")
    if not legend_ok:
        issues.append(f"legend:多系列图但图例项仅 {legend_items}")

    theme_issue = theme_problem(measured.get("app_lang"), measured.get("paper_bgcolor"), source)
    if theme_issue:
        issues.append(theme_issue)

    return AestheticsReport(
        no_label_overlap=over_pairs == 0,
        no_text_truncation=not truncations,
        axes_legend_complete=bool(axes_ok and legend_ok),
        theme_consistent=theme_issue is None,
        max_overlap_ratio=worst,
        issues=issues,
    )


# 在页面内一次性量测：文本矩形、溢出、刻度/图例、主题、Plotly 轨迹与数据点
MEASURE_JS = r"""
(() => {
  const root = document.querySelector(__SEL__);
  if (!root) return { found: false };
  const rects = [];
  const oriented = [];
  const orRect = el => {
    // 旋转感知的文字矩形：中心取实测中心，宽高取 getBBox（不含自身旋转），角度取屏幕矩阵
    const r = el.getBoundingClientRect();
    const out = { cx: r.x + r.width / 2, cy: r.y + r.height / 2,
                  w: r.width, h: r.height, th: 0,
                  kind: '', text: (el.textContent || '').trim().slice(0, 18) };
    if (typeof SVGElement === 'undefined' || !(el instanceof SVGElement) || !el.getBBox) return out;
    const list = el.transform && el.transform.baseVal;
    const ctm = el.getScreenCTM ? el.getScreenCTM() : null;
    if (!list || !list.numberOfItems || !ctm) return out;
    const own = list.consolidate().matrix;
    if (!own || (!own.b && !own.c)) return out;          // 没旋转：就是普通外接矩形
    const b = el.getBBox();
    if (!(b.width > 0) || !(b.height > 0)) return out;
    out.w = b.width * Math.hypot(ctm.a, ctm.b);
    out.h = b.height * Math.hypot(ctm.c, ctm.d);
    out.th = Math.atan2(ctm.b, ctm.a);
    return out;
  };
  const push = (el, kind) => {
    const r = el.getBoundingClientRect();
    if (r.width > 1 && r.height > 1) {
      rects.push({ x: r.x, y: r.y, width: r.width, height: r.height, kind,
                   text: (el.textContent || '').trim().slice(0, 24) });
      const q = orRect(el);
      q.kind = kind;
      oriented.push(q);
    }
  };
  root.querySelectorAll('.xtick text').forEach(e => push(e, 'xtick'));
  root.querySelectorAll('.ytick text').forEach(e => push(e, 'ytick'));
  root.querySelectorAll('.legend text').forEach(e => push(e, 'legend'));

  // 交叠判定（旋转感知）：把文字还原成「中心 + 自身宽高 + 旋转角」的有向矩形，
  // 用凸多边形裁剪求真实交集面积。轴对齐外接矩形对斜排刻度（Plotly tickangle）必然相交，
  // 实测手动热力图按外接矩形算出的 37.7% 「交叠」在有向几何下是 0%（纯误报）。
  const quadOf = q => {
    const c = Math.cos(q.th), s = Math.sin(q.th), hw = q.w / 2, hh = q.h / 2;
    return [[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]]
      .map(p => [q.cx + p[0] * c - p[1] * s, q.cy + p[0] * s + p[1] * c]);
  };
  const clipBy = (poly, a, n) => {
    const out = [];
    for (let i = 0; i < poly.length; i++) {
      const cur = poly[i], nxt = poly[(i + 1) % poly.length];
      const dc = (cur[0] - a[0]) * n[0] + (cur[1] - a[1]) * n[1];
      const dn = (nxt[0] - a[0]) * n[0] + (nxt[1] - a[1]) * n[1];
      if (dc <= 1e-9) out.push(cur);
      if ((dc < 0 && dn > 0) || (dc > 0 && dn < 0)) {
        const t = dc / (dc - dn);
        out.push([cur[0] + (nxt[0] - cur[0]) * t, cur[1] + (nxt[1] - cur[1]) * t]);
      }
    }
    return out;
  };
  const polyArea = poly => {
    let sum = 0;
    for (let i = 0; i < poly.length; i++) {
      const q = poly[(i + 1) % poly.length];
      sum += poly[i][0] * q[1] - q[0] * poly[i][1];
    }
    return Math.abs(sum) / 2;
  };
  const interArea = (A, B) => {
    let cx = 0, cy = 0;
    for (const p of A) { cx += p[0]; cy += p[1]; }
    cx /= A.length; cy /= A.length;
    let poly = B;
    for (let i = 0; i < A.length && poly.length; i++) {
      const p = A[i], q = A[(i + 1) % A.length];
      const ex = q[0] - p[0], ey = q[1] - p[1];
      let n = [-ey, ex];
      if ((cx - p[0]) * n[0] + (cy - p[1]) * n[1] < 0) n = [ey, -ex];
      poly = clipBy(poly, p, n);
    }
    return poly.length ? polyArea(poly) : 0;
  };
  const overlaps = [];
  for (let i = 0; i < oriented.length; i++) {
    for (let j = i + 1; j < oriented.length; j++) {
      const a = oriented[i], b = oriented[j];
      if (Math.abs(a.cx - b.cx) > a.w + b.w || Math.abs(a.cy - b.cy) > a.h + b.h) continue;
      const smaller = Math.min(a.w * a.h, b.w * b.h);
      if (smaller <= 0) continue;
      const ratio = interArea(quadOf(a), quadOf(b)) / smaller;
      if (ratio >= 0.001) overlaps.push({ a: a.text, b: b.text, ratio: +ratio.toFixed(4) });
    }
  }
  overlaps.sort((p, q) => q.ratio - p.ratio);

  // 文本截断分两类量测：
  //   * HTML 元素（题目/轴标题等）→ CSS 溢出语义：scrollWidth/clientWidth、scrollHeight/clientHeight；
  //   * SVG <text>（Plotly 的刻度、轴标题、图例全部是 SVG 文本）→ SVG 没有 CSS 溢出语义，
  //     scrollWidth/clientWidth 在浏览器里返回无意义值（实测 sw=17 > cw=4 之类的假阳性），
  //     因此改判「文字矩形是否越出容器边界」——越出即代表元素级截图（成片底图）会把文字裁掉。
  const rootRect = root.getBoundingClientRect();
  const truncations = [];
  const svgLabel = el => {
    const own = el.getAttribute('class');
    if (own) return '.' + own.split(' ')[0];
    const g = el.closest('g');
    const gcls = g && g.getAttribute('class');
    return gcls ? '.' + gcls.split(' ')[0] : 'text';
  };
  root.querySelectorAll('text, span, label').forEach(el => {
    const content = (el.textContent || '').trim();
    if (!content) return;
    if (typeof SVGElement !== 'undefined' && el instanceof SVGElement) {
      const r = el.getBoundingClientRect();
      if (r.width <= 1 || r.height <= 1) return;
      const overX = Math.max(rootRect.left - r.left, r.right - rootRect.right);
      const overY = Math.max(rootRect.top - r.top, r.bottom - rootRect.bottom);
      if (overX > 1) {
        truncations.push({ label: svgLabel(el), text: content.slice(0, 24),
                           sw: Math.round(r.width), cw: Math.max(1, Math.round(r.width - overX)), sh: 0, ch: 0 });
      }
      if (overY > 1) {
        truncations.push({ label: svgLabel(el), text: content.slice(0, 24),
                           sw: 0, cw: 0, sh: Math.round(r.height), ch: Math.max(1, Math.round(r.height - overY)) });
      }
      return;
    }
    const sw = el.scrollWidth, cw = el.clientWidth, sh = el.scrollHeight, ch = el.clientHeight;
    if (cw > 0 && ch > 0 && (sw > cw + 1 || sh > ch + 1)) {
      const cls = (typeof el.className === 'string' && el.className)
        ? '.' + el.className.split(' ')[0] : el.tagName;
      truncations.push({ label: cls, text: content.slice(0, 24), sw, cw, sh, ch });
    }
  });

  const graph = root.querySelector('.js-plotly-plot') || root;
  const len = a => Array.isArray(a) ? a.length : 0;
  const traces = ((graph.data) || []).map(t => {
    const type = t.type || 'scatter';
    if (type === 'heatmap' || type === 'histogram2d') {
      const z = t.z || [], rows = z.length, cols = (rows && Array.isArray(z[0])) ? z[0].length : 0;
      return { type: 'heatmap', points: rows * cols, method: 'cells' };
    }
    if (type === 'parcoords') {
      const d = t.dimensions || [], rows = d.length ? len(d[0].values) : 0;
      return { type: 'parallel', points: rows * d.length, method: 'cells' };
    }
    if (type === 'scatterpolar') return { type: 'radar', points: len(t.r), method: 'plotly_points' };
    if (type === 'pie') return { type: 'pie', points: len(t.labels), method: 'plotly_points' };
    if (type === 'box') return { type: 'box', points: Math.max(len(t.y), len(t.x)), method: 'plotly_points' };
    if (type === 'histogram') return { type: 'histogram', points: len(t.x), method: 'plotly_points' };
    return { type, points: Math.max(len(t.x), len(t.y), len(t.values)), method: 'plotly_points' };
  });

  const app = document.querySelector('.app');
  const layout = graph._fullLayout || {};
  return {
    found: true,
    rects,
    overlaps: overlaps.slice(0, 24),
    truncations: truncations.slice(0, 12),
    tickCount: { x: root.querySelectorAll('.xtick').length, y: root.querySelectorAll('.ytick').length },
    legendItems: root.querySelectorAll('.legend .traces').length || root.querySelectorAll('.legend text').length,
    traceCount: traces.length,
    traces,
    has_xtitle: !!(root.querySelector('.xtitle') || root.querySelector('.xaxislayer-above .xtitle')),
    has_ytitle: !!(root.querySelector('.ytitle') || root.querySelector('.yaxislayer-above .ytitle')),
    app_lang: app ? app.getAttribute('data-lang') : null,
    paper_bgcolor: layout.paper_bgcolor || null,
  };
})()
"""


def measure(page, container_selector: str, source: str) -> dict:
    """在页面里量测指定容器；返回原始量测 + ``report`` 判定结果。"""
    payload = page.evaluate(MEASURE_JS.replace("__SEL__", json.dumps(container_selector)))
    if not payload or not payload.get("found"):
        empty = AestheticsReport(False, False, False, False, 1.0,
                                 [f"container_missing:{container_selector}"])
        return {"found": False, "report": empty.to_dict()}
    payload["report"] = evaluate(payload, source).to_dict()
    return payload

