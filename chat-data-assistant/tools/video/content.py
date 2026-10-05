"""读取并校验内容定义（``content/scenes.toml`` 与 ``content/candidates.toml``）。

只读、零第三方依赖（标准库 ``tomllib``），校验规则与
``specs/001-intro-video-generator/data-model.md`` §1~§2 一一对应。
"""
from __future__ import annotations

import hashlib
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import settings as S

ASCII_WORD_RE = re.compile(r"[A-Za-z]{2,}")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
# 中文文案里允许出现的专有名词（FR-021 的「语言纯净」白名单）
ZH_WHITELIST = ("SQL", "AI", "Plotly", "Chat", "Data", "XRD", "XPS", "PCT", "DSC", "TPD", "PNG", "MOF")
AGGREGATE_HINTS = ("多少", "总计", "统计", "有几个", "一共", "总数", "how many", "count of", "total number")


class ContentError(Exception):
    """内容定义非法（退出码 5）。code 用于脚本判定，message 面向人工。"""

    def __init__(self, code: str, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class LocalizedText:
    zh: str
    en: str

    def for_lang(self, lang: str) -> str:
        return self.zh if lang == "zh" else self.en


@dataclass(frozen=True)
class Shot:
    id: str
    order: int
    kind: str
    title: LocalizedText
    narration: LocalizedText
    subtitle: LocalizedText | None = None
    source: str | None = None
    duration_sec: float | None = None
    zoom: str = "in"
    background: str = "plate"

    def text_for(self, lang: str) -> str:
        return (self.subtitle or self.narration).for_lang(lang)


@dataclass(frozen=True)
class Candidate:
    id: str
    prompt: LocalizedText
    expect_chart: bool = True
    notes: str = ""
    # 出图控制（FR-016：内容侧可编辑、无需改生成逻辑）：
    #   ai_recommend=False → 取消勾选界面里的「使用 AI 推荐的图表配置」；
    #   chart_type         → 手动指定图型（前提是 ai_recommend=False）；
    #   fields             → 在该图型行里依次挑选字段列（如 ("year", "paper_count")）。
    ai_recommend: bool = True
    chart_type: str | None = None
    fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class Manual:
    id: str
    chart_type: str
    title: LocalizedText
    x_field: str | None = None
    y_fields: tuple[str, ...] = ()
    z_field: str | None = None
    size_field: str | None = None
    color_field: str | None = None
    notes: str = ""


@dataclass
class Content:
    version: str
    title: LocalizedText
    target_duration: tuple[float, float]
    languages: tuple[str, ...]
    shots: list[Shot]
    candidates: list[Candidate]
    manuals: list[Manual]
    short_sha: str
    paths: dict[str, Path] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def version_label(self) -> str:
        return f"scenes={self.version},candidates={self.version}"

    def shot(self, shot_id: str) -> Shot:
        for s in self.shots:
            if s.id == shot_id:
                return s
        raise ContentError("source_not_found", f"分镜 id 不存在：{shot_id}")

    def candidate(self, cid: str) -> Candidate:
        for c in self.candidates:
            if c.id == cid:
                return c
        raise ContentError("source_not_found", f"候选 id 不存在：{cid}")

    def manual(self, mid: str) -> Manual:
        for m in self.manuals:
            if m.id == mid:
                return m
        raise ContentError("source_not_found", f"手动绘图 id 不存在：{mid}")


# ── 读取 ────────────────────────────────────────────────────────────────────
def load_content(content_dir: Path | None = None) -> Content:
    root = Path(content_dir or S.CONTENT_DIR)
    scenes_path = root / "scenes.toml"
    candidates_path = root / "candidates.toml"
    for p in (scenes_path, candidates_path):
        if not p.is_file():
            raise ContentError("content_missing", f"内容定义文件不存在：{p}")

    scenes = _read_toml(scenes_path)
    cands = _read_toml(candidates_path)
    warnings: list[str] = []

    meta = scenes.get("meta") or {}
    version = _require_str(meta, "version", scenes_path)
    title = _localized(meta.get("title"), f"{scenes_path.name} meta.title")
    target = meta.get("target_duration_sec") or list(S.DEFAULT_TARGET_DURATION)
    if (not isinstance(target, list) or len(target) != 2
            or not all(isinstance(x, (int, float)) for x in target)
            or not (10 <= target[0] < target[1] <= 900)):
        raise ContentError("content_invalid", "meta.target_duration_sec 必须是 [min, max]，且 10 <= min < max <= 900")
    languages = tuple(meta.get("languages") or S.LANGUAGES)
    if languages != S.LANGUAGES:
        raise ContentError("content_invalid", f"meta.languages 必须是 {list(S.LANGUAGES)}")

    shots = [_with_source_file(scenes_path, _shot, raw, i, warnings)
             for i, raw in enumerate(scenes.get("shot") or [], start=1)]
    if not shots:
        raise ContentError("content_invalid", "scenes.toml 至少需要一个 [[shot]]")

    candidates = [_with_source_file(candidates_path, _candidate, raw)
                  for raw in cands.get("candidate") or []]
    manuals = [_with_source_file(candidates_path, _manual, raw)
               for raw in cands.get("manual") or []]

    try:
        _validate_structure(shots, candidates, manuals, warnings)
    except ContentError as exc:
        if exc.message.startswith(scenes_path.name):
            raise
        raise ContentError(exc.code,
                           f"{scenes_path.name} + {candidates_path.name} → {exc.message}") from exc
    short_sha = _content_sha([scenes_path, candidates_path])
    return Content(
        version=version, title=title, target_duration=(float(target[0]), float(target[1])),
        languages=languages, shots=shots, candidates=candidates, manuals=manuals,
        short_sha=short_sha, paths={"scenes": scenes_path, "candidates": candidates_path},
        warnings=warnings,
    )


# ── 解析辅助 ────────────────────────────────────────────────────────────────
def _with_source_file(path: Path, fn, *args):
    """把「文件 → 分镜/候选 id → 字段」三段定位补齐（contracts/content-definition.md §错误处理）。"""
    try:
        return fn(*args)
    except ContentError as exc:
        if exc.message.startswith(path.name):
            raise
        raise ContentError(exc.code, f"{path.name} → {exc.message}") from exc


def _read_toml(path: Path) -> dict:
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ContentError("content_invalid", f"{path.name} TOML 语法错误：{exc}") from exc


def _require_str(table: dict, key: str, path: Path) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ContentError("content_invalid", f"{path.name} 缺少非空字符串字段 `{key}`")
    return value.strip()


def _localized(raw: object, where: str, required: bool = True) -> LocalizedText | None:
    if raw is None:
        if required:
            raise ContentError("content_invalid", f"{where} 必须提供 {{ zh, en }} 双语文本")
        return None
    if not isinstance(raw, dict):
        raise ContentError("content_invalid", f"{where} 必须是表（table），形如 [x.title] zh=... en=...")
    zh = str(raw.get("zh") or "").strip()
    en = str(raw.get("en") or "").strip()
    if not zh or not en:
        raise ContentError("content_invalid", f"{where} 的中英文本必须同时非空（zh={bool(zh)}, en={bool(en)}）")
    text = LocalizedText(zh, en)
    validate_localized_text(text, where)
    return text


def validate_localized_text(text: LocalizedText, where: str) -> None:
    """双语纯净性（FR-021）：中文不得出现英文单词，英文不得出现中日韩字符。"""
    for word in ASCII_WORD_RE.findall(text.zh):
        if not any(word.upper().startswith(w.upper()) for w in ZH_WHITELIST):
            raise ContentError("content_invalid", f"{where}.zh 出现英文单词「{word}」，应改为中文")
    if CJK_RE.search(text.en):
        raise ContentError("content_invalid", f"{where}.en 出现中文字符，应改为纯英文")


def localize(text: LocalizedText, lang: str) -> str:
    """按语言投影（FR-021：结构不变，仅文案不同）。"""
    if lang not in S.LANGUAGES:
        raise ContentError("content_invalid", f"不支持的语言：{lang!r}（可选 {list(S.LANGUAGES)}）")
    return text.for_lang(lang)


def _shot(raw: dict, index: int, warnings: list[str]) -> Shot:
    sid = str(raw.get("id") or "")
    if not re.match(S.ID_RE, sid):
        raise ContentError("content_invalid", f"第 {index} 个 [[shot]] 的 id 非法（需匹配 {S.ID_RE}）：{sid!r}")
    kind = str(raw.get("kind") or "")
    if kind not in S.SHOT_KINDS:
        raise ContentError("content_invalid", f"分镜 {sid} 的 kind 非法：{kind!r}（可选 {list(S.SHOT_KINDS)}）")
    order = raw.get("order", index)
    if not isinstance(order, int) or order < 1:
        raise ContentError("content_invalid", f"分镜 {sid} 的 order 必须是 ≥1 的整数")

    title = _localized(raw.get("title"), f"分镜 {sid}.title")
    narration = _localized(raw.get("narration"), f"分镜 {sid}.narration")
    subtitle = _localized(raw.get("subtitle"), f"分镜 {sid}.subtitle", required=False)

    source = raw.get("source")
    if source is not None and not isinstance(source, str):
        raise ContentError("content_invalid", f"分镜 {sid} 的 source 必须是字符串")
    if kind in ("chart_showcase", "manual_plot") and not source:
        raise ContentError("content_invalid", f"分镜 {sid}（kind={kind}）必须提供 source")
    if kind not in ("chart_showcase", "manual_plot") and source:
        raise ContentError("content_invalid", f"分镜 {sid}（kind={kind}）不得提供 source")

    duration = raw.get("duration_sec")
    if duration is not None:
        if not isinstance(duration, (int, float)) or not (S.SHOT_MIN_SEC <= float(duration) <= S.SHOT_MAX_SEC):
            raise ContentError(
                "duration_out_of_range",
                f"分镜 {sid} 的 duration_sec 必须在 {S.SHOT_MIN_SEC}~{S.SHOT_MAX_SEC} 秒之间",
            )
        duration = float(duration)

    zoom = str(raw.get("zoom") or "in")
    if zoom not in ("in", "out", "pan_left", "pan_right"):
        raise ContentError("content_invalid", f"分镜 {sid} 的 zoom 非法：{zoom!r}")
    background = str(raw.get("background") or "plate")
    if background not in ("plate", "blur_plate"):
        raise ContentError("content_invalid", f"分镜 {sid} 的 background 非法：{background!r}")

    if len(narration.zh) > 220 or len(narration.en) > 400:
        warnings.append(f"narration_length: 分镜 {sid} 旁白偏长（zh {len(narration.zh)} / en {len(narration.en)} 字符）")
    if len(title.zh) > 28 or len(title.en) > 48:
        warnings.append(f"title_length: 分镜 {sid} 标题偏长，可能溢出画面")
    return Shot(id=sid, order=order, kind=kind, title=title, narration=narration, subtitle=subtitle,
                source=source, duration_sec=duration, zoom=zoom, background=background)


def _candidate(raw: dict) -> Candidate:
    cid = str(raw.get("id") or "")
    if not re.match(S.ID_RE, cid):
        raise ContentError("content_invalid", f"[[candidate]] 的 id 非法：{cid!r}")
    prompt = _localized(raw.get("prompt"), f"候选 {cid}.prompt")
    ai_recommend = bool(raw.get("ai_recommend", True))
    chart_type = raw.get("chart_type")
    if chart_type is not None:
        chart_type = str(chart_type)
        if chart_type not in S.CHART_TYPES:
            raise ContentError(
                "content_invalid",
                f"候选 {cid} 的 chart_type 非法：{chart_type!r}（可选 {list(S.CHART_TYPES)}）")
    raw_fields = raw.get("fields") or []
    if not isinstance(raw_fields, list) or any(
            not isinstance(v, str) or not v.strip() for v in raw_fields):
        raise ContentError("content_invalid",
                           f"候选 {cid} 的 fields 必须是字符串数组：{raw_fields!r}")
    if (chart_type or raw_fields) and ai_recommend:
        raise ContentError(
            "content_invalid",
            f"候选 {cid} 指定了 chart_type/fields，必须同时 ai_recommend = false"
            "（手动选型的前提是关闭 AI 推荐）")
    return Candidate(id=cid, prompt=prompt,
                     expect_chart=bool(raw.get("expect_chart", True)),
                     notes=str(raw.get("notes") or ""),
                     ai_recommend=ai_recommend,
                     chart_type=chart_type,
                     fields=tuple(str(v) for v in raw_fields))


def _manual(raw: dict) -> Manual:
    mid = str(raw.get("id") or "")
    if not re.match(S.ID_RE, mid):
        raise ContentError("content_invalid", f"[[manual]] 的 id 非法：{mid!r}")
    chart_type = str(raw.get("chart_type") or "")
    if chart_type not in S.MANUAL_CHART_TYPES:
        raise ContentError(
            "content_invalid",
            f"手动绘图 {mid} 的 chart_type 非法：{chart_type!r}（手动绘图器仅支持 {list(S.MANUAL_CHART_TYPES)}）",
        )
    title = _localized(raw.get("title"), f"手动绘图 {mid}.title")

    x_field = raw.get("x_field")
    y_fields = tuple(raw.get("y_fields") or ())
    z_field = raw.get("z_field")
    size_field = raw.get("size_field")
    color_field = raw.get("color_field")

    for name, value in (("x_field", x_field), ("z_field", z_field),
                        ("size_field", size_field), ("color_field", color_field)):
        if value is not None and value not in S.MANUAL_FIELD_KEYS:
            raise ContentError("field_not_found",
                               f"手动绘图 {mid} 的 {name}={value!r} 不在可用字段 {list(S.MANUAL_FIELD_KEYS)} 中")
    for value in y_fields:
        if value not in S.MANUAL_FIELD_KEYS:
            raise ContentError("field_not_found",
                               f"手动绘图 {mid} 的 y_fields 含未知字段 {value!r}（可用 {list(S.MANUAL_FIELD_KEYS)}）")

    if chart_type in ("heatmap", "parallel", "radar"):
        pass                                    # 自动使用全部数值列
    elif chart_type == "pie":
        if not x_field:
            raise ContentError("content_invalid", f"手动绘图 {mid}（pie）必须提供 x_field")
    elif chart_type == "scatter3d":
        if not (x_field and y_fields and z_field):
            raise ContentError("content_invalid", f"手动绘图 {mid}（scatter3d）必须提供 x_field / y_fields / z_field")
    elif chart_type == "bubble":
        if not (x_field and y_fields and size_field and color_field):
            raise ContentError("content_invalid",
                               f"手动绘图 {mid}（bubble）必须提供 x_field / y_fields / size_field / color_field")
    else:
        if not (x_field and y_fields):
            raise ContentError("content_invalid", f"手动绘图 {mid}（{chart_type}）必须提供 x_field / y_fields")

    return Manual(id=mid, chart_type=chart_type, title=title, x_field=x_field, y_fields=y_fields,
                  z_field=z_field, size_field=size_field, color_field=color_field,
                  notes=str(raw.get("notes") or ""))


# ── 结构校验（跨字段规则，data-model.md §2.2「校验的跨字段规则」）────────────
def _validate_structure(shots: list[Shot], candidates: list[Candidate],
                        manuals: list[Manual], warnings: list[str]) -> None:
    ids = [s.id for s in shots]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise ContentError("content_invalid", f"分镜 id 重复：{sorted(dup)}")
    orders = sorted(s.order for s in shots)
    if orders != list(range(1, len(shots) + 1)):
        raise ContentError("order_not_contiguous",
                           f"分镜 order 必须是 1..{len(shots)} 连续无重复，当前为 {orders}")

    by_kind: dict[str, list[Shot]] = {}
    for s in shots:
        by_kind.setdefault(s.kind, []).append(s)

    n_chart = len(by_kind.get("chart_showcase", []))
    if n_chart < S.MIN_CHART_SHOTS:
        raise ContentError("insufficient_qualified_scenes",
                           f"kind=chart_showcase 的分镜必须 ≥ {S.MIN_CHART_SHOTS}，当前 {n_chart}")
    n_manual = len(by_kind.get("manual_plot", []))
    if n_manual < S.MIN_MANUAL_SHOTS:
        raise ContentError("insufficient_manual_sources",
                           f"kind=manual_plot 的分镜必须 ≥ {S.MIN_MANUAL_SHOTS}，当前 {n_manual}")
    if not by_kind.get("ui_explain"):
        raise ContentError("content_invalid", "必须至少有一个 kind=ui_explain 分镜（FR-015）")
    n_bilingual = len(by_kind.get("bilingual_demo", []))
    if n_bilingual != 1:
        raise ContentError("content_invalid", f"kind=bilingual_demo 必须恰好 1 个，当前 {n_bilingual}")

    cand_ids = {c.id for c in candidates}
    manual_ids = {m.id for m in manuals}
    clash = cand_ids & manual_ids
    if clash:
        raise ContentError("content_invalid", f"候选与手动绘图 id 冲突：{sorted(clash)}")
    for s in shots:
        if s.kind == "chart_showcase" and s.source not in cand_ids:
            raise ContentError("source_not_found",
                               f"分镜 {s.id} 的 source={s.source!r} 不在 candidates.toml 的 [[candidate]] 中")
        if s.kind == "manual_plot" and s.source not in manual_ids:
            raise ContentError("source_not_found",
                               f"分镜 {s.id} 的 source={s.source!r} 不在 candidates.toml 的 [[manual]] 中")

    if not (8 <= len(candidates) <= 20):
        raise ContentError("content_invalid", f"[[candidate]] 数量必须在 8~20 之间，当前 {len(candidates)}")
    if len(manuals) < 1:
        raise ContentError("insufficient_manual_sources", "[[manual]] 至少需要 1 条")

    for c in candidates:
        if any(h in c.prompt.zh.lower() for h in AGGREGATE_HINTS) or \
           any(h in c.prompt.en.lower() for h in AGGREGATE_HINTS):
            warnings.append(
                f"prompt_not_visual: 候选 {c.id} 的提问偏聚合统计，可能只返回单行结果（intent=data），"
                "建议改为「分组 / 趋势 / 对比 / 分布」句式"
            )


def _content_sha(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for p in paths:
        digest.update(p.read_bytes())
    return digest.hexdigest()[:7]


def content_sha256(paths: list[Path]) -> dict[str, str]:
    """完整 sha256（写入 manifest.content_sha256）。"""
    return {p.stem: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def reload_short_sha(content: Content) -> str:
    return _content_sha([content.paths["scenes"], content.paths["candidates"]])



