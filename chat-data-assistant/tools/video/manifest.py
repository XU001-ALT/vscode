"""运行目录、sha256 清单与「不可覆盖」保护（FR-022、SC-010）。"""
from __future__ import annotations

import hashlib
import json
import shutil
import time
from datetime import datetime
from pathlib import Path

from . import settings as S
from . import safety

SUBDIRS = ("plates", "clips", "audio", "subs", "segments")


class ManifestError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_run_id(short_sha: str) -> str:
    return f"{now_stamp()}-{short_sha}"


def run_dir(run_id: str) -> Path:
    return Path(S.RUNS_DIR) / run_id


def ensure_run_dir(run_id: str, *, allow_existing: bool = False) -> Path:
    """创建运行目录；已有 manifest.json 时拒绝（除非 allow_existing）。"""
    path = run_dir(run_id)
    manifest = path / "manifest.json"
    if manifest.exists() and not allow_existing:
        raise ManifestError("path_exists", f"该运行目录已存在产物清单，拒绝覆盖：{manifest}")
    for name in SUBDIRS:
        (path / name).mkdir(parents=True, exist_ok=True)
    return path


def latest_run_dir() -> Path:
    root = Path(S.RUNS_DIR)
    if not root.is_dir():
        raise ManifestError("run_not_found", f"尚未有运行产物：{root}")
    candidates = sorted([p for p in root.iterdir() if p.is_dir()])
    if not candidates:
        raise ManifestError("run_not_found", f"尚未有运行产物：{root}")
    return candidates[-1]


def resolve_run_dir(run_id: str | None) -> Path:
    return run_dir(run_id) if run_id else latest_run_dir()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict, *, sanitize: bool = True) -> Path:
    """写 JSON；默认拒绝覆盖，且先做敏感信息扫描（命中则拒绝落盘）。"""
    path = Path(path)
    if path.exists():
        raise ManifestError("path_exists", f"文件已存在，拒绝覆盖：{path}")
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    findings = safety.scan_text(text)
    if findings:
        raise ManifestError(
            "sensitive_in_report",
            f"待写入 {path.name} 的内容含敏感信息（{findings[0]['kind']}: {findings[0]['excerpt']}），已中止",
        )
    if sanitize:
        text = safety.sanitize(text)
    path.write_text(text, encoding="utf-8")
    return path


def update_json(path: Path, payload: dict) -> Path:
    """就地覆盖（仅用于 verify 更新 manifest）；同样先扫敏感信息。"""
    path = Path(path)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    findings = safety.scan_text(text)
    if findings:
        raise ManifestError("sensitive_in_report",
                            f"{path.name} 更新内容含敏感信息（{findings[0]['kind']}），已中止")
    path.write_text(text, encoding="utf-8")
    return path


def read_json(path: Path) -> dict:
    path = Path(path)
    if not path.is_file():
        raise ManifestError("run_not_found", f"找不到文件：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def report_path(run_dir_path: Path) -> Path:
    return Path(run_dir_path) / "report.json"


def manifest_path(run_dir_path: Path) -> Path:
    return Path(run_dir_path) / "manifest.json"


def existing_video_hashes(exclude_run: str | None = None) -> dict[str, str]:
    """既有成片的 sha256（V12 的历史不变校验依据）。"""
    root = Path(S.RUNS_DIR)
    result: dict[str, str] = {}
    if not root.is_dir():
        return result
    for run in sorted(p for p in root.iterdir() if p.is_dir()):
        if exclude_run and run.name == exclude_run:
            continue
        for video in sorted(run.glob("demo-*.mp4")):
            result[f"{run.name}/{video.name}"] = sha256_file(video)
    return result


def publish(run_dir_path: Path, *, apply: bool = False,
            target_dir: Path | None = None) -> dict:
    """把成片发布到前端演示位；默认 dry-run，apply 时先备份既有文件。"""
    run_path = Path(run_dir_path)
    dest = Path(target_dir or S.PUBLIC_DIR)
    stamp = now_stamp()
    actions: list[dict] = []
    for lang, name in S.PUBLISH_TARGETS.items():
        src = run_path / f"demo-{lang}.mp4"
        if not src.is_file():
            continue
        dst = dest / name
        backup = dest / f"{dst.stem}.{stamp}.bak{dst.suffix}"
        actions.append({"source": str(src), "target": str(dst),
                        "backup": str(backup) if dst.exists() else None,
                        "exists": dst.exists()})
    if not actions:
        raise ManifestError("publish_nothing", f"{run_path} 下没有可发布的 demo-*.mp4")

    result = {"applied": bool(apply), "targets": [], "backups": [], "at": iso_now()}
    if not apply:
        return result

    if not dest.is_dir():
        raise ManifestError("publish_failed", f"发布目标目录不存在：{dest}")
    for action in actions:
        src, dst = Path(action["source"]), Path(action["target"])
        try:
            if dst.exists():
                shutil.copy2(dst, Path(action["backup"]))
                result["backups"].append(action["backup"])
            shutil.copy2(src, dst)
        except OSError as exc:
            raise ManifestError("publish_failed", f"发布失败（{dst}）：{exc}") from exc
        result["targets"].append(str(dst))

    # 一并发布海报（若产物目录里有）
    for lang, poster in S.POSTER_TARGETS.items():
        src_poster = run_path / f"poster-{lang}.jpg"
        if src_poster.is_file():
            shutil.copy2(src_poster, dest / poster)
    return result


def touch_stamp() -> float:
    return time.time()
