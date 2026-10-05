"""CLI 入口：doctor / probe / build / verify / publish（contracts/cli.md）。

用法（工作目录为 chat-data-assistant/）：

    venv\\Scripts\\python.exe -m tools.video.cli doctor
    venv\\Scripts\\python.exe -m tools.video.cli probe
    venv\\Scripts\\python.exe -m tools.video.cli build
    venv\\Scripts\\python.exe -m tools.video.cli verify
    venv\\Scripts\\python.exe -m tools.video.cli publish --apply

不接受任何凭据参数：模型凭据一律由后端服务端持有（Constitution II）。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import (
    aesthetics, capture, classify, ffmpeg, manifest,
    preflight, render, safety, select, subtitles, tts, ui_surface,
)
from . import settings as S
from . import content as content_mod


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tools.video.cli",
        description="客户演示视频生成器（真实界面采集 → 判定筛选 → 合成双语成片）",
    )
    parser.add_argument("command", choices=["doctor", "probe", "build", "verify", "publish"])
    parser.add_argument("--content-dir", type=Path, default=None, help="内容定义目录（含 scenes.toml / candidates.toml）")
    parser.add_argument("--runs-dir", type=Path, default=None, help="运行产物根目录")
    parser.add_argument("--run-id", default=None, help="沿用既有运行目录（build/verify/publish）")
    parser.add_argument("--min-data-points", type=int, default=None, help="「数据点较多」阈值，默认 10")
    parser.add_argument("--frontend-url", default=None)
    parser.add_argument("--backend-url", default=None)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--headless", dest="headed", action="store_false", help="无头模式（默认）")
    group.add_argument("--headed", dest="headed", action="store_true", help="显示浏览器窗口")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果摘要")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--timeout", type=int, default=None, help="整体运行上限（秒），默认 1800")

    parser.add_argument("--only", default=None, help="probe：只测 id 含该子串的候选")
    parser.add_argument("--candidate-limit", type=int, default=None, help="probe：最多测 N 条候选")
    parser.add_argument("--retries", type=int, default=1, help="probe：单条失败重试次数")
    parser.add_argument("--no-clips", action="store_true", help="probe：不录制交互片段")
    parser.add_argument("--api-cross-check", action="store_true",
                        help="probe：额外用 /api/query 交叉验证（多花一倍模型调用，默认关闭）")
    parser.add_argument("--lang", default="both", choices=["both", "zh", "en"], help="build：产出语言")
    parser.add_argument("--dry-run", action="store_true", help="build：只打印将要执行的命令")
    parser.add_argument("--strict", action="store_true", help="verify：告警也计为失败")
    parser.add_argument("--apply", action="store_true", help="publish：真正写入（默认 dry-run）")
    parser.add_argument("--target", type=Path, default=None, help="publish：目标目录，默认 frontend/public")
    return parser


# ── 通用辅助 ────────────────────────────────────────────────────────────────
def apply_overrides(args) -> None:
    if args.runs_dir:
        S.RUNS_DIR = Path(args.runs_dir)
    if args.content_dir:
        S.CONTENT_DIR = Path(args.content_dir)
    if args.min_data_points:
        S.MIN_DATA_POINTS = int(args.min_data_points)
    if args.frontend_url:
        S.FRONTEND_URL = args.frontend_url
    if args.backend_url:
        S.BACKEND_URL = args.backend_url


def emit(args, payload: dict, lines: list[str] | None = None) -> None:
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for line in lines or []:
            print(line)


def fail(code: int, where: str, message: str) -> int:
    print(f"[E{code}] {where}: {message}", file=sys.stderr)
    return code


def load_content_or_exit(args) -> tuple[content_mod.Content | None, int]:
    try:
        content = content_mod.load_content(args.content_dir)
    except content_mod.ContentError as exc:
        return None, fail(S.EXIT_CONTENT, exc.code, exc.message)
    for warning in content.warnings:
        print(f"WARN {warning}")
    return content, S.EXIT_OK


def tool_versions() -> dict:
    versions = {"python": sys.version.split()[0]}
    try:
        versions["ffmpeg"] = (ffmpeg.version().split(" Copyright")[0] or "").replace("ffmpeg version ", "")
    except Exception:  # noqa: BLE001
        versions["ffmpeg"] = "unknown"
    for name, module in (("playwright", "playwright"), ("edge_tts", "edge_tts")):
        try:
            versions[name] = __import__("importlib.metadata", fromlist=["version"]).version(module)
        except Exception:  # noqa: BLE001
            versions[name] = "unknown"
    return versions


# ── doctor ──────────────────────────────────────────────────────────────────
def cmd_doctor(args) -> int:
    checks, tables = preflight.run_all(frontend_url=args.frontend_url, backend_url=args.backend_url,
                                      with_tts=True)
    anchor_hits: dict[str, bool] = {}
    anchor_error: str | None = None

    if checks[1].ok:                        # 前端可达才去核对锚点
        try:
            with capture.browser_session(headed=args.headed) as (_browser, _context, page):
                capture.open_app(page)
                anchor_hits, _ = ui_surface.check_page(page)
        except ui_surface.UiSurfaceDrift as drift:
            anchor_error = str(drift)
        except Exception as exc:            # noqa: BLE001 - 浏览器问题本身由 browser 项报告
            anchor_error = f"锚点检查跳过：{type(exc).__name__}: {exc}"

    passed = sum(1 for c in checks if c.ok)
    lines: list[str] = []
    for check in checks:
        mark = "ok  " if check.ok else "FAIL"
        lines.append(f"[{mark}] {check.id:<10} {check.detail}")
    if anchor_error:
        lines.append(f"[FAIL] ui_surface {anchor_error}")
    else:
        missing_soft = ui_surface.missing_soft(anchor_hits) if anchor_hits else []
        lines.append(f"[ok  ] ui_surface 命中 {len(anchor_hits)}/{len(ui_surface.ANCHORS)} 锚点"
                     + (f"，软锚点未命中：{missing_soft}" if missing_soft else ""))
    lines.append(f"PASS {passed}/{len(checks)}")

    payload = {
        "checks": [c.to_dict() for c in checks],
        "tables": tables,
        "ui_surface": {"hits": anchor_hits, "error": anchor_error},
        "passed": passed, "total": len(checks),
    }
    emit(args, payload, lines)

    if anchor_error:
        return S.EXIT_UI_SURFACE
    missing = preflight.failed_ids(checks)
    if missing:
        print(f"缺失/失败项：{missing}", file=sys.stderr)
        return S.EXIT_PREFLIGHT
    return S.EXIT_OK


# ── probe ───────────────────────────────────────────────────────────────────
def _capture_plate_rel(plate: str | None, run_path: Path) -> str | None:
    """把绝对底图路径转换成 report.json 里的相对路径（plates/xxx.png）。"""
    if not plate:
        return None
    try:
        return Path(plate).resolve().relative_to(Path(run_path).resolve()).as_posix()
    except ValueError:
        return None


def _probe_one(page, *, item_id: str, source: str, prompt: dict,
               run_path: Path, args, question: str = "", manual=None,
               candidate=None) -> dict:
    """实测一条候选（含重试），返回完整 CandidateResult。"""
    plate_name = f"{item_id}.png" if source == "query" else f"manual_{item_id}.png"
    snapshot = None
    last_error: Exception | None = None
    for _attempt in range(max(1, args.retries + 1)):
        try:
            if source == "query":
                snapshot = capture.ask_query(
                    page, question, out_dir=run_path / "plates", plate_name=plate_name,
                    lang="zh", with_clips=not args.no_clips, clip_dir=run_path / "clips",
                    ai_recommend=getattr(candidate, "ai_recommend", True),
                    chart_type=getattr(candidate, "chart_type", None),
                    fields=getattr(candidate, "fields", ()))
            else:
                snapshot = capture.capture_manual(
                    page, manual, out_dir=run_path / "plates", plate_name=plate_name, lang="zh")
            break
        except Exception as exc:            # noqa: BLE001 - 单条失败不应中断整轮探测
            last_error = exc
    if snapshot is None:
        snapshot = capture.CaptureSnapshot(error_text=safety.sanitize(f"capture_failed: {last_error}"))

    if source == "manual":
        if snapshot.has_plotly:
            ui_surface.check_manual(page)   # 手动绘图区锚点（.manual-plot-demo）
    elif snapshot.has_plotly:
        ui_surface.check_chart(page)        # 出图后才存在的锚点，缺失即视为链路漂移

    api = None
    if source == "query" and getattr(args, "api_cross_check", False):
        api = classify.api_cross_check(question, lang="zh", backend_url=args.backend_url)

    result = classify.classify(
        snapshot.to_dict(), source=source, prompt=prompt,
        plate_path=_capture_plate_rel(snapshot.plate, run_path),
        capture_ms=snapshot.elapsed_ms, api=api,
        manual_chart_type=(manual.chart_type if manual else None),
    )
    result["id"] = item_id
    result["aesthetics"] = snapshot.aesthetics or {
        "no_label_overlap": False, "no_text_truncation": False, "axes_legend_complete": False,
        "theme_consistent": False, "max_overlap_ratio": 1.0, "issues": ["aesthetics_missing"],
    }
    return result


def cmd_probe(args) -> int:
    started = time.time()
    content, code = load_content_or_exit(args)
    if content is None:
        return code

    checks, _tables = preflight.run_all(frontend_url=args.frontend_url, backend_url=args.backend_url)
    run_id = manifest.new_run_id(content.short_sha)
    run_path = Path(S.RUNS_DIR) / run_id
    failed = preflight.failed_ids(checks)

    if failed:
        # 前置条件不满足：只写报告与日志，绝不创建成片路径（FR-023）
        run_path.mkdir(parents=True, exist_ok=True)
        manifest.write_json(run_path / "report.json", {
            "schema_version": "1.0.0", "run_id": run_id, "generated_at": manifest.iso_now(),
            "tool_versions": tool_versions(), "preflight": [c.to_dict() for c in checks],
            "candidates": [],
            "summary": {"total": 0, "chart_ok": 0, "table_only": 0, "failed": 0, "recommended": 0,
                        "manual_recommended": 0, "issues": [f"preflight_failed:{failed}"]},
            "seeded_from": None,
        })
        for check in checks:
            if not check.ok:
                print(f"[FAIL] {check.id}: {check.detail}", file=sys.stderr)
        return fail(S.EXIT_PREFLIGHT, "preflight", f"前置条件未满足：{failed}")

    run_path = manifest.ensure_run_dir(run_id)
    candidates = content.candidates
    if args.only:
        candidates = [c for c in candidates if args.only in c.id]
    if args.candidate_limit:
        candidates = candidates[: args.candidate_limit]

    total = len(candidates) + len(content.manuals)
    results: list[dict] = []
    print(f"run_id {run_id}", file=sys.stderr)
    with capture.browser_session(headed=args.headed) as (_browser, _context, page):
        capture.open_app(page)
        ui_surface.check_page(page)
        index = 0
        for candidate in candidates:
            index += 1
            print(f"  [{index}/{total}] {candidate.id} ...", file=sys.stderr, end="", flush=True)
            result = _probe_one(page, item_id=candidate.id, source="query",
                                prompt={"zh": candidate.prompt.zh, "en": candidate.prompt.en},
                                question=candidate.prompt.for_lang("zh"), run_path=run_path,
                                args=args, candidate=candidate)
            results.append(result)
            print(f" {result['verdict']} points={result['data_points']} "
                  f"aesthetic={'pass' if select.aesthetics_passed(result['aesthetics']) else 'fail'}",
                  file=sys.stderr)
        for manual in content.manuals:
            index += 1
            print(f"  [{index}/{total}] {manual.id} (manual) ...", file=sys.stderr, end="", flush=True)
            result = _probe_one(page, item_id=manual.id, source="manual",
                                prompt={"zh": manual.title.zh, "en": manual.title.en},
                                run_path=run_path, args=args, manual=manual)
            results.append(result)
            print(f" {result['verdict']} points={result['data_points']} "
                  f"aesthetic={'pass' if select.aesthetics_passed(result['aesthetics']) else 'fail'}",
                  file=sys.stderr)

    ranked = select.rank_results(results, S.MIN_DATA_POINTS)
    summary = dict(ranked["summary"])
    summary["issues"] = list(ranked["issues"])
    summary["runtime_sec"] = round(time.time() - started, 1)
    manifest.write_json(run_path / "report.json", {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "generated_at": manifest.iso_now(),
        "tool_versions": tool_versions(),
        "preflight": [c.to_dict() for c in checks],
        "candidates": results,
        "summary": summary,
        "seeded_from": None,
    })

    lines = [f"run_id   {run_id}",
             f"{'id':<20}{'verdict':<12}{'intent':<8}{'chart':<11}{'points':<8}{'method':<9}"
             f"{'aesthetic':<10}rank"]
    for result in sorted(results, key=lambda r: (r["rank"] == 0, r["rank"] or 999, r["id"])):
        lines.append(
            f"{result['id']:<20}{result['verdict']:<12}{str(result['intent'] or '-'):<8}"
            f"{str(result['chart_type'] or '-'):<11}{result['data_points']:<8}"
            f"{result['data_points_method']:<9}"
            f"{('pass' if select.aesthetics_passed(result['aesthetics']) else 'fail'):<10}{result['rank']}")
    lines.append(f"summary  total={summary['total']} chart_ok={summary['chart_ok']} "
                 f"table_only={summary['table_only']} failed={summary['failed']} "
                 f"recommended={summary['recommended']} (manual={summary['manual_recommended']})")
    for issue in summary["issues"]:
        lines.append(f"WARN {issue}")
    for result in results:
        for tip in select.suggestions(result):
            lines.append(f"  tip {result['id']}: {tip}")
    emit(args, {"run_id": run_id, "report": str(run_path / "report.json"), **summary}, lines)
    return S.EXIT_OK


# ── build ───────────────────────────────────────────────────────────────────
def _plan_shot_plates(content, run_path: Path, report: dict, lang: str, page) -> dict[str, str]:
    """为每个分镜准备背景底图：图表候选的静帧，或整页截图（界面说明 / 语言切换 / 收尾）。"""
    plates: dict[str, str] = {}
    by_id = {c["id"]: c for c in report["candidates"]}
    fallback = next((c for c in report["candidates"] if c.get("recommended")), None)
    if fallback is None:
        raise manifest.ManifestError("insufficient_qualified_scenes", "报告中没有可用的推荐候选，无法生成底图")

    for shot in sorted(content.shots, key=lambda s: s.order):
        if shot.kind in ("chart_showcase", "manual_plot"):
            entry = by_id.get(shot.source)
            if entry is None or not entry.get("plate_path"):
                raise manifest.ManifestError(
                    "source_not_found", f"分镜 {shot.id} 的 source={shot.source} 在报告中没有可用底图")
            if entry.get("verdict") != "chart_ok":
                raise manifest.ManifestError(
                    "source_not_qualified", f"分镜 {shot.id} 的 source={shot.source} 判定为 {entry.get('verdict')}，不得进片")
            plates[shot.id] = str(run_path / entry["plate_path"])
        elif shot.kind == "ui_explain":
            question = fallback["prompt"]["zh"]
            plates[shot.id] = capture.capture_page_plate(
                page, out_dir=run_path / "plates", name=f"page-ui-{lang}.png", lang=lang,
                question=question)
        elif shot.kind == "bilingual_demo":
            plates[shot.id] = capture.capture_page_plate(
                page, out_dir=run_path / "plates", name=f"page-lang-{lang}.png", lang=lang,
                toggle_lang=True, question=fallback["prompt"]["zh"])
        else:  # outro 等
            plates[shot.id] = str(run_path / fallback["plate_path"])
    return plates


def _render_language(content, run_path: Path, report: dict, lang: str, plates: dict[str, str],
                     *, started: float, dry_run: bool, engine=None) -> dict:
    """渲染一种语言的全部分镜并合成成片，返回 producedVideo 记录。"""
    shots = sorted(content.shots, key=lambda s: s.order)
    renders: list[render.ShotRender] = []
    shot_entries: list[dict] = []
    covered_total = 0.0
    audio_total = 0.0
    cursor = 0.0

    for shot in shots:
        text = shot.text_for(lang)                 # text_for 已按语言投影，返回纯文本
        stem = f"{lang}-{shot.order:02d}-{shot.id}"
        audio_path = run_path / "audio" / f"{stem}.mp3"
        ass_path = run_path / "subs" / f"{stem}.ass"
        srt_path = run_path / "subs" / f"{stem}.srt"
        result = tts.synthesize_shot(text, lang, audio_path, engine=engine)
        cues = subtitles.build_shot_subtitles(text, lang, result.words, result.duration)
        subtitles.write_subtitles(cues, ass_path, srt_path)
        duration = shot.duration_sec or (result.duration + 0.8)
        duration = float(min(max(duration, S.SHOT_MIN_SEC), S.SHOT_MAX_SEC))
        covered_total += sum(max(0.0, c.end - c.start) for c in cues)
        audio_total += result.duration

        renders.append(render.ShotRender(
            shot_id=shot.id, language=lang, plate=Path(plates[shot.id]), audio=audio_path,
            ass=ass_path, duration=duration, zoom=shot.zoom, background=shot.background,
            start_sec=cursor))
        shot_entries.append({
            "id": shot.id, "order": shot.order, "start_sec": round(cursor, 3),
            "duration_sec": round(duration, 3),
            "candidate_id": shot.source,
            "plate_sha256": manifest.sha256_file(Path(plates[shot.id])),
            "narration_chars": len(text),
        })
        cursor += duration

    segments: list[Path] = []
    for item in renders:
        out = run_path / "segments" / f"{item.language}-{item.shot_id}.mp4"
        segments.append(render.build_segment(item, out, dry_run=dry_run))
    video = run_path / f"demo-{lang}.mp4"
    if not dry_run:
        video, join_mode = render.join_segments(segments, video, [r.duration for r in renders])
        render.extract_poster(video, run_path / f"poster-{lang}.jpg", at=min(2.0, renders[0].duration / 2))
    else:
        join_mode = "dry-run"

    info = ffmpeg.media_info(video) if not dry_run else None
    coverage = round(min(1.0, covered_total / audio_total), 4) if audio_total else 0.0
    return {
        "language": lang,
        "path": f"demo-{lang}.mp4",
        "sha256": manifest.sha256_file(video) if not dry_run else "0" * 64,
        "bytes": video.stat().st_size if not dry_run else 0,
        "duration_sec": info.duration if info else round(cursor, 3),
        "width": info.width if info else S.WIDTH,
        "height": info.height if info else S.HEIGHT,
        "fps": info.fps if info else float(S.FPS),
        "video_codec": info.video_codec if info else "h264",
        "audio_codec": info.audio_codec if info else "aac",
        "pix_fmt": info.pix_fmt if info else "yuv420p",
        "container": "mp4",
        "scene_count": len(renders),
        "chart_background_ratio": 1.0,
        "subtitle_coverage": coverage,
        "sensitive_findings": 0,
        "created_at": manifest.iso_now(),
        "run_id": run_path.name,
        "source_shots": shot_entries,
        "_join_mode": join_mode,
    }


def cmd_build(args) -> int:
    started = time.time()
    content, code = load_content_or_exit(args)
    if content is None:
        return code
    try:
        run_path = manifest.resolve_run_dir(args.run_id)
        report = manifest.read_json(manifest.report_path(run_path))
    except manifest.ManifestError as exc:
        return fail(S.EXIT_CONTENT, exc.code, exc.message)

    # FR-022：历史产物不可覆盖。先判存在性再谈内容合格度，避免白跑一遍采集/渲染
    if manifest.manifest_path(run_path).exists():
        return fail(S.EXIT_RENDER, "path_exists",
                    f"{run_path.name} 已存在 manifest.json，拒绝覆盖历史产物（FR-022）")

    recommended = [c for c in report.get("candidates", []) if c.get("recommended")]
    chart_n = sum(1 for c in recommended if c.get("source") == "query")
    manual_n = sum(1 for c in recommended if c.get("source") == "manual")
    if chart_n < S.MIN_CHART_SHOTS or manual_n < S.MIN_MANUAL_SHOTS:
        return fail(S.EXIT_CONTENT, "insufficient_qualified_scenes",
                    f"合格场景不足：问答出图 {chart_n}（需 ≥{S.MIN_CHART_SHOTS}）、"
                    f"手动绘图 {manual_n}（需 ≥{S.MIN_MANUAL_SHOTS}）；请调整 content/candidates.toml 或阈值后重跑 probe")

    langs = ["zh", "en"] if args.lang == "both" else [args.lang]
    if args.dry_run:
        lines = [f"run_id {run_path.name}", "将执行：TTS → 字幕 → 分镜渲染 → xfade 拼接 → manifest"]
        for lang in langs:
            for shot in sorted(content.shots, key=lambda s: s.order):
                lines.append(f"  segment {lang} #{shot.order} {shot.id} "
                             f"plate={shot.source or shot.kind} zoom={shot.zoom} bg={shot.background}")
            lines.append(f"  output {run_path / f'demo-{lang}.mp4'}")
        emit(args, {"run_id": run_path.name, "languages": langs, "dry_run": True}, lines)
        return S.EXIT_OK

    produced: list[dict] = []
    sensitive = 0
    plate_sets: dict[str, dict[str, str]] = {}
    with capture.browser_session(headed=args.headed) as (_browser, _context, page):
        capture.open_app(page)
        ui_surface.check_page(page)
        for lang in langs:
            plate_sets[lang] = _plan_shot_plates(content, run_path, report, lang, page)
    # 浏览器必须先关闭：TTS 走 asyncio.run，不能在 Playwright 的同步事件循环里执行
    for lang in langs:
        record = _render_language(content, run_path, report, lang, plate_sets[lang],
                                  started=started, dry_run=False)
        record.pop("_join_mode", None)
        produced.append(record)
        print(f"rendered demo-{lang}.mp4 ({record['duration_sec']}s, "
              f"{record['scene_count']} 镜)", file=sys.stderr)

    for shot in content.shots:
        for lang in langs:
            sensitive += safety.count_findings(shot.text_for(lang))
    sensitive += safety.count_findings(json.dumps(report["candidates"], ensure_ascii=False))
    for record in produced:
        record["sensitive_findings"] = sensitive

    shots_entry = produced[0]["source_shots"] if produced else []
    manifest_payload = {
        "schema_version": "1.0.0",
        "run_id": run_path.name,
        "created_at": manifest.iso_now(),
        "tool_versions": tool_versions(),
        "content_sha256": content_mod.content_sha256(list(content.paths.values())),
        "content_version": content.version_label,
        "source_report_sha256": manifest.sha256_file(manifest.report_path(run_path)),
        "preflight": report.get("preflight", []),
        "shots": shots_entry,
        "produced_videos": produced,
        "verification": [],
        "verification_passed": False,
        "sensitive_findings": sensitive,
        "published": None,
        "summary_runtime_sec": round(time.time() - started, 1),
    }
    manifest.write_json(manifest.manifest_path(run_path), manifest_payload)

    lines = [f"run_id {run_path.name}"]
    for record in produced:
        lines.append(f"  demo-{record['language']}.mp4  {record['duration_sec']}s  "
                     f"{record['width']}x{record['height']}@{record['fps']}fps  "
                     f"{record['bytes'] / 1e6:.1f} MB  字幕覆盖 {record['subtitle_coverage']:.0%}")
    lines.append(f"manifest  {manifest.manifest_path(run_path)}")
    emit(args, {"run_id": run_path.name, "produced": produced,
                "manifest": str(manifest.manifest_path(run_path))}, lines)
    return S.EXIT_OK


# ── verify ──────────────────────────────────────────────────────────────────
def _check(check_id: str, ok: bool, detail: str, measured: float | None = None,
           blocking: bool = True) -> dict:
    return {"id": check_id, "ok": bool(ok), "detail": detail,
            "measured": measured, "blocking": blocking}


def _load_hash_baseline() -> tuple[Path, dict]:
    path = Path(S.RUNS_DIR) / ".video-hashes.json"
    if path.is_file():
        try:
            return path, json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return path, {}


def _verify_core_checks(content, run_path: Path, data: dict, report: dict) -> list[dict]:
    """V8~V12：内部质量项。"""
    by_id = {c["id"]: c for c in report.get("candidates", [])}
    videos = data.get("produced_videos", [])
    shots = data.get("shots", [])
    checks: list[dict] = []

    low, high = content.target_duration
    tol = S.DURATION_TOLERANCE
    durations = [float(v.get("duration_sec") or 0) for v in videos]
    ok8 = bool(videos) and all(low * (1 - tol) <= d <= high * (1 + tol) for d in durations)
    checks.append(_check("V8", ok8,
                         f"时长 {[round(d, 1) for d in durations]}s，目标区间 {low:.0f}~{high:.0f}s"
                         f"（±{tol:.0%}）", max(durations or [0])))

    orders = [[s["order"] for s in v.get("source_shots", [])] for v in videos]
    counts = [int(v.get("scene_count") or 0) for v in videos]
    same_order = bool(orders) and all(o == orders[0] for o in orders)
    ok9 = len(videos) <= 1 or (len(set(counts)) == 1 and same_order)
    checks.append(_check("V9", ok9, f"分镜数 {counts}，顺序一致={same_order}",
                         float(counts[0]) if counts else None))

    chart_shots = sum(1 for s in shots if by_id.get(s.get("candidate_id") or "", {}).get("source") == "query")
    manual_shots = sum(1 for s in shots if by_id.get(s.get("candidate_id") or "", {}).get("source") == "manual")
    ok10 = chart_shots >= S.MIN_CHART_SHOTS and manual_shots >= S.MIN_MANUAL_SHOTS
    checks.append(_check("V10", ok10,
                         f"问答出图 {chart_shots}（≥{S.MIN_CHART_SHOTS}）、手动绘图 {manual_shots}"
                         f"（≥{S.MIN_MANUAL_SHOTS}）", float(chart_shots)))

    bad: list[str] = []
    for entry in shots:
        cid = entry.get("candidate_id")
        if not cid:
            continue
        item = by_id.get(cid)
        if item is None:
            bad.append(f"{cid}(missing)")
            continue
        aesthetic_ok = select.aesthetics_passed(item.get("aesthetics"))
        if (item.get("verdict") != "chart_ok"
                or int(item.get("data_points") or 0) < S.MIN_DATA_POINTS
                or not aesthetic_ok):
            bad.append(f"{cid}(verdict={item.get('verdict')},points={item.get('data_points')},"
                       f"aesthetic={aesthetic_ok})")
    checks.append(_check("V11", not bad,
                         "全部进片图表满足 数据点≥阈值 且 美观四项全过" if not bad else f"不合格：{bad}",
                         float(S.MIN_DATA_POINTS)))

    baseline_path, baseline = _load_hash_baseline()
    current = manifest.existing_video_hashes(exclude_run=run_path.name)
    changed = [k for k, v in baseline.items() if k in current and current[k] != v]
    missing = [k for k in baseline if k not in current]
    ok12 = not changed and not missing
    checks.append(_check("V12", ok12,
                         "历史成片 sha256 全部未变" if ok12 else f"变化={changed} 缺失={missing}"))
    return checks


def _verify_output_checks(run_path: Path, data: dict) -> list[dict]:
    """SC-002 / SC-007 / SC-008 / SC-009 / SC-012：面向成片本身的判据。"""
    videos = data.get("produced_videos", [])
    checks: list[dict] = []

    playable: list[str] = []
    resolution: list[str] = []
    for video in videos:
        path = run_path / video["path"]
        try:
            info = ffmpeg.media_info(path)
        except Exception as exc:            # noqa: BLE001
            playable.append(f"{video['path']}({exc})")
            continue
        if not (info.video_codec == "h264" and info.audio_codec == "aac" and info.pix_fmt == "yuv420p"
                and info.faststart and info.has_audio):
            playable.append(f"{video['path']}({info.video_codec}/{info.audio_codec}/{info.pix_fmt}"
                            f"/faststart={info.faststart})")
        if info.width < S.WIDTH or info.height < S.HEIGHT or info.fps < S.FPS:
            resolution.append(f"{video['path']}({info.width}x{info.height}@{info.fps})")
    checks.append(_check("SC-002", not playable,
                         "h264+aac+yuv420p+faststart 全部满足" if not playable else f"不满足：{playable}"))
    checks.append(_check("SC-009", not resolution,
                         f"分辨率/帧率 {[(v.get('width'), v.get('height'), v.get('fps')) for v in videos]}"
                         if not resolution else f"不满足：{resolution}",
                         float(min((float(v.get('fps') or 0) for v in videos), default=0))))

    ratios = [float(v.get("chart_background_ratio") or 0) for v in videos]
    ok07 = bool(ratios) and all(r >= S.CHART_BACKGROUND_MIN_RATIO for r in ratios)
    checks.append(_check("SC-007", ok07,
                         f"图表背景占比 {ratios}（要求 ≥{S.CHART_BACKGROUND_MIN_RATIO}）", min(ratios or [0])))

    coverages = [float(v.get("subtitle_coverage") or 0) for v in videos]
    ok08 = bool(coverages) and all(c >= 0.999 for c in coverages)
    checks.append(_check("SC-008", ok08, f"字幕覆盖 {coverages}（要求 100%）", min(coverages or [0])))

    findings = sum(int(v.get("sensitive_findings") or 0) for v in videos)
    for srt in sorted((run_path / "subs").glob("*.srt")):
        findings += safety.count_findings(srt.read_text(encoding="utf-8"))
    findings += safety.count_findings(manifest.manifest_path(run_path).read_text(encoding="utf-8"))
    checks.append(_check("SC-012", findings == 0, f"敏感信息检出 {findings} 项（要求 0）", float(findings)))
    return checks


def cmd_verify(args) -> int:
    content, code = load_content_or_exit(args)
    if content is None:
        return code
    try:
        run_path = manifest.resolve_run_dir(args.run_id)
        mpath = manifest.manifest_path(run_path)
        data = manifest.read_json(mpath)
        report = manifest.read_json(manifest.report_path(run_path))
    except manifest.ManifestError as exc:
        return fail(S.EXIT_VERIFY, exc.code, exc.message)

    checks = _verify_core_checks(content, run_path, data, report)
    checks += _verify_output_checks(run_path, data)

    data["verification"] = checks
    data["verification_passed"] = all(c["ok"] for c in checks if c["blocking"])
    manifest.update_json(mpath, data)

    baseline_path, baseline = _load_hash_baseline()
    baseline.update(manifest.existing_video_hashes())
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    passed = sum(1 for c in checks if c["ok"])
    lines = [f"run_id {run_path.name}"]
    for item in checks:
        lines.append(f"[{'ok  ' if item['ok'] else 'FAIL'}] {item['id']:<7} {item['detail']}")
    lines.append(f"PASS {passed}/{len(checks)} | verification_passed={data['verification_passed']}")
    emit(args, {"run_id": run_path.name, "verification": checks,
                "verification_passed": data["verification_passed"]}, lines)

    if not data["verification_passed"] or (args.strict and passed != len(checks)):
        return S.EXIT_VERIFY
    return S.EXIT_OK


# ── publish ─────────────────────────────────────────────────────────────────
def cmd_publish(args) -> int:
    try:
        run_path = manifest.resolve_run_dir(args.run_id)
    except manifest.ManifestError as exc:
        return fail(S.EXIT_PUBLISH, exc.code, exc.message)
    try:
        result = manifest.publish(run_path, apply=args.apply, target_dir=args.target)
    except manifest.ManifestError as exc:
        return fail(S.EXIT_PUBLISH, exc.code, exc.message)

    lines = [f"{'已发布' if args.apply else 'DRY-RUN'} run_id {run_path.name} → "
             f"{args.target or S.PUBLIC_DIR}"]
    for lang, name in S.PUBLISH_TARGETS.items():
        src = run_path / f"demo-{lang}.mp4"
        if src.is_file():
            lines.append(f"  copy {src.name} → {name}"
                         + ("（目标已存在，先备份为 demo.<时间戳>.bak.mp4）"
                            if (Path(args.target or S.PUBLIC_DIR) / name).exists() else ""))
    if not args.apply:
        lines.append("提示：加 --apply 才会真正写入（默认 dry-run）")
    if args.apply:
        manifest_payload_path = manifest.manifest_path(run_path)
        if manifest_payload_path.is_file():
            payload = manifest.read_json(manifest_payload_path)
            payload["published"] = result
            manifest.update_json(manifest_payload_path, payload)
    emit(args, result, lines)
    return S.EXIT_OK


# ── 入口 ────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    apply_overrides(args)
    if args.timeout:
        S.RUN_TIMEOUT_SEC = int(args.timeout)

    handlers = {"doctor": cmd_doctor, "probe": cmd_probe, "build": cmd_build,
                "verify": cmd_verify, "publish": cmd_publish}
    try:
        return handlers[args.command](args)
    except content_mod.ContentError as exc:
        return fail(S.EXIT_CONTENT, exc.code, exc.message)
    except ui_surface.UiSurfaceDrift as exc:
        return fail(S.EXIT_UI_SURFACE, exc.code, str(exc))
    except manifest.ManifestError as exc:
        code = S.EXIT_RENDER if exc.code == "path_exists" else S.EXIT_CONTENT
        return fail(code, exc.code, exc.message)
    except ffmpeg.FfmpegError as exc:
        detail = exc.message + (f"\n{exc.stderr}" if exc.stderr else "")
        return fail(S.EXIT_RENDER, exc.code, detail)
    except capture.CaptureError as exc:
        code = S.EXIT_UI_SURFACE if exc.code.startswith("ui_surface") else S.EXIT_PREFLIGHT
        return fail(code, exc.code, exc.message)
    except KeyboardInterrupt:
        print("已中断（未产生半成品）", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())








