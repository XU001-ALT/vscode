"""可用性判定（FR-006/FR-007）：成功出图 / 仅表格 / 失败 + 图表类型 + 数据点数。

判定规则见 research.md R2；数据点与图表类型取自真实界面的 Plotly 轨迹（DOM 证据），
可选地与会话接口响应对照（双源交叉）。
"""
from __future__ import annotations

from . import settings as S
from . import safety

# 界面错误文案 → 既有 error_code 体系（与前端 errKey 列表保持一致）
ERROR_PATTERNS = (
    ("llm_auth", ("api key", "密钥", "鉴权", "unauthorized", "401", "authentication", "invalid_api")),
    ("llm_timeout", ("timed out", "timeout", "超时")),
    ("llm_conn", ("connection", "连接失败", "network", "网络", "ssl", "dns", "无法连接")),
    ("no_schema", ("表结构", "schema", "尚未就绪")),
    ("sql_failed", ("syntax error", "sql", "permission denied", "权限", "permission")),
    ("empty_question", ("问题不能为空", "empty question")),
    ("server_busy", ("busy", "繁忙", "too many requests", "429")),
)

TRACE_TYPE_MAP = {
    "scatter": "scatter", "bar": "bar", "box": "box", "pie": "pie",
    "histogram": "histogram", "heatmap": "heatmap", "histogram2d": "heatmap",
    "parcoords": "parallel", "scatterpolar": "radar", "scatter3d": "scatter3d",
    "surface": "scatter3d", "area": "area", "line": "line",
}


def error_code_from_text(text: str | None) -> str | None:
    if not text:
        return None
    low = text.lower()
    for code, needles in ERROR_PATTERNS:
        if any(n in low for n in needles):
            return code
    return "unknown"


def normalize_chart_type(traces: list[dict]) -> str | None:
    if not traces:
        return None
    first = traces[0]
    raw = str(first.get("type") or "").lower()
    if raw == "scatter":
        mode = str(first.get("mode") or "")
        if "lines" in mode and "markers" not in mode:
            return "line"
        if first.get("fill"):
            return "area"
        return "scatter"
    return TRACE_TYPE_MAP.get(raw, raw or None)


def data_points_from_traces(traces: list[dict]) -> tuple[int, str]:
    """返回（数据点数, 计数方式）。多列自动图型按 cells 计。"""
    if not traces:
        return 0, "row_count"
    best = max(int(t.get("points") or 0) for t in traces)
    method = "cells" if any(str(t.get("method")) == "cells" for t in traces) else "row_count"
    return best, method


def classify(snapshot: dict, *, source: str, prompt: dict, min_data_points: int | None = None,
             plate_path: str | None = None, capture_ms: int = 0, api: dict | None = None,
             manual_chart_type: str | None = None) -> dict:
    """产出一条 CandidateResult（缺少 aesthetics / recommended / rank，由调用方补齐）。

    - ``snapshot``：capture.py 采集的界面证据（has_plotly / traces / error_text / answer_text）
    - ``api``：可选的 ``/api/query`` 响应对照（双源交叉）
    """
    traces = list(snapshot.get("traces") or [])
    has_plotly = bool(snapshot.get("has_plotly"))
    error_text = safety.sanitize((snapshot.get("error_text") or "").strip())
    answer_text = (snapshot.get("answer_text") or "").strip()

    chart_type = manual_chart_type or normalize_chart_type(traces)
    data_points, method = data_points_from_traces(traces)
    if source == "manual":
        points_text = str(snapshot.get("record_count") or "").strip()
        if points_text.isdigit():
            data_points, method = int(points_text), "manual"
        elif data_points:
            method = "manual"

    api_ok = bool(api.get("ok")) if api else not error_text
    error_code = (api or {}).get("error_code") or error_code_from_text(error_text)
    intent = (api or {}).get("intent")
    if intent is None:
        intent = "chart" if has_plotly else ("chat" if answer_text else None)

    # 三态判定（FR-006）：成功出图 / 仅表格 / 失败
    if error_text and not has_plotly:
        verdict = "failed"
    elif has_plotly and data_points >= 1:
        verdict = "chart_ok"
    elif error_text:
        verdict = "failed"
    elif api is not None and not api_ok:
        verdict = "failed"
    elif api is not None and api.get("row_count") == 1 and answer_text:
        verdict = "table_only"
    elif answer_text or (api is not None and api.get("columns")):
        verdict = "table_only"
    else:
        verdict = "failed"
        error_code = error_code or "empty_result"

    return {
        "id": "",
        "source": source,
        "prompt": prompt,
        "verdict": verdict,
        "intent": intent,
        "chart_type": chart_type,
        "data_points": int(data_points),
        "data_points_method": method if method in S.DATA_POINTS_METHODS else "row_count",
        "api_ok": api_ok,
        "error_code": error_code,
        "error_excerpt": error_text[:200] or None,
        "plate_path": plate_path,
        "recommended": False,
        "rank": 0,
        "capture_ms": int(capture_ms),
    }


def api_cross_check(question: str, lang: str = "zh", backend_url: str | None = None,
                    timeout: int = 120) -> dict | None:
    """可选的双源交叉：直接问一次 ``/api/query`` 取 intent / row_count / error_code。"""
    from . import preflight
    base = (backend_url or S.BACKEND_URL).rstrip("/")
    status, payload = preflight._http_post_json(  # noqa: SLF001 - 复用同一封装
        f"{base}/api/query", {"question": question, "lang": lang}, timeout=timeout
    )
    if status != 200:
        return None
    return {
        "ok": bool(payload.get("ok")),
        "error_code": payload.get("error_code"),
        "intent": payload.get("intent"),
        "row_count": payload.get("row_count"),
        "columns": payload.get("columns") or [],
    }

