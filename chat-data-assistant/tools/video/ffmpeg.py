"""ffmpeg / ffprobe 封装：命令执行、媒体信息探测、能力检查、滤镜路径转义。"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import settings as S


class FfmpegError(Exception):
    def __init__(self, code: str, message: str, stderr: str = ""):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.stderr = stderr


@dataclass(frozen=True)
class MediaInfo:
    path: str
    duration: float
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: str
    pix_fmt: str
    has_audio: bool
    faststart: bool


def run(args: list[str], *, timeout: int = 1800, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        [str(a) for a in args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )
    if check and proc.returncode != 0:
        tail = "\n".join((proc.stderr or "").strip().splitlines()[-12:])
        raise FfmpegError("ffmpeg_failed", f"命令失败（exit {proc.returncode}）：{' '.join(str(a) for a in args[:3])} …", tail)
    return proc


def version() -> str:
    proc = run([S.FFMPEG_BIN, "-version"], timeout=60, check=False)
    first = (proc.stdout or proc.stderr or "").splitlines()
    return first[0].strip() if first else ""


def capabilities() -> dict[str, bool]:
    enc = run([S.FFMPEG_BIN, "-hide_banner", "-encoders"], timeout=60, check=False).stdout or ""
    flt = run([S.FFMPEG_BIN, "-hide_banner", "-filters"], timeout=60, check=False).stdout or ""
    text = enc + flt
    return {
        "libx264": "libx264" in enc,
        "aac": " aac " in enc or "aac" in enc,
        "zoompan": "zoompan" in flt,
        "xfade": "xfade" in flt,
        "subtitles": "subtitles" in flt or "ass" in flt,
        "raw": bool(text),
    }


def probe_json(path: str | Path) -> dict:
    proc = run([S.FFPROBE_BIN, "-v", "error", "-print_format", "json",
                "-show_format", "-show_streams", str(path)], timeout=120, check=False)
    if proc.returncode != 0:
        raise FfmpegError("probe_failed", f"ffprobe 无法解析 {path}", proc.stderr or "")
    return json.loads(proc.stdout or "{}")


def _parse_fps(value: str) -> float:
    if not value or value == "0/0":
        return 0.0
    if "/" in value:
        num, den = value.split("/", 1)
        try:
            return float(num) / float(den) if float(den) else 0.0
        except ValueError:
            return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def media_info(path: str | Path) -> MediaInfo:
    data = probe_json(path)
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
    duration = float((data.get("format") or {}).get("duration")
                     or video.get("duration") or audio.get("duration") or 0.0)
    fps = _parse_fps(video.get("avg_frame_rate") or video.get("r_frame_rate") or "")
    faststart = _has_faststart(Path(path))
    return MediaInfo(
        path=str(path), duration=round(duration, 3),
        width=int(video.get("width") or 0), height=int(video.get("height") or 0),
        fps=round(fps, 3), video_codec=str(video.get("codec_name") or ""),
        audio_codec=str(audio.get("codec_name") or ""), pix_fmt=str(video.get("pix_fmt") or ""),
        has_audio=bool(audio), faststart=faststart,
    )


def _has_faststart(path: Path) -> bool:
    """moov 在 mdat 之前即视为 faststart。"""
    try:
        with path.open("rb") as fh:
            head = fh.read(1 << 20)
    except OSError:
        return False
    moov = head.find(b"moov")
    mdat = head.find(b"mdat")
    if moov < 0 or mdat < 0:
        return moov >= 0
    return moov < mdat


def escape_filter_path(path: str | Path) -> str:
    """把 Windows 路径转成 FFmpeg 滤镜参数里的安全写法。

    实测 ffmpeg 9.0.1：裸写 ``C\\:/Windows/Fonts`` 或 ``'C:/Windows/Fonts'`` 都会被滤镜图
    解析器报 ``No option name near '/Windows/Fonts'``；只有**单引号包裹 + 双反斜杠转义冒号**
    （``'C\\\\:/Windows/Fonts'``）能正确解析，因此这里统一输出该形式（正斜杠 + 全量转义冒号）。
    """
    text = str(path).replace("\\", "/").replace("'", r"\'").replace(":", r"\:")
    return f"'{text}'"


def duration_of(path: str | Path) -> float:
    return media_info(path).duration
