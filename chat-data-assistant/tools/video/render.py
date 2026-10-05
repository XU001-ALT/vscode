"""分镜渲染与成片合成（research R6）：zoompan 推镜 + 字幕烧录 → xfade 拼接。

``render.py`` 只构建命令，实际执行交给 ``ffmpeg.py``（便于 ``--dry-run`` 与单测）。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import ffmpeg, settings as S


@dataclass
class ShotRender:
    shot_id: str
    language: str
    plate: Path
    audio: Path
    ass: Path
    duration: float
    zoom: str = "in"
    background: str = "plate"
    segment: Path | None = None
    start_sec: float = 0.0


def plate_normalize_filter() -> str:
    """把任意比例的底图等比归一化到 zoompan 之前的 16:9 画布。

    底图是界面元素级截图（比例随内容变化，例如 1180x1294 ≈ 0.91），而 zoompan 只按
    ``s=WxH`` 输出、不会保持输入比例：直接送进去会把图横向拉宽（用户实测反馈
    「截图比例不对、像是没截全」）。这里先等比缩放 + 居中补边到 16:9，并按推镜幅度
    预留安全边距（``S.PLATE_SAFE_MARGIN``），使推镜最大时也裁不到图形与轴标签。
    """
    canvas_w, canvas_h = int(S.WIDTH * 1.25), int(S.HEIGHT * 1.25)          # 2400x1350
    margin = max(0.0, min(0.2, S.PLATE_SAFE_MARGIN))
    inner_w = max(2, int(round(canvas_w * (1 - 2 * margin))))
    inner_h = max(2, int(round(canvas_h * (1 - 2 * margin))))
    return (f"scale={inner_w}:{inner_h}:force_original_aspect_ratio=decrease,"
            f"pad={canvas_w}:{canvas_h}:(ow-iw)/2:(oh-ih)/2:color={S.PLATE_PAD_COLOR},")


def _video_filter(shot: ShotRender, frames: int) -> str:
    """构造 [0:v] 链：等比取景 → (可选模糊) → zoompan 推镜 → 字幕烧录。"""
    zoom, d = shot.zoom, max(1, frames)
    if zoom == "out":
        z = f"max({S.ZOOM_END}-{(S.ZOOM_END - S.ZOOM_START):.3f}*on/{d},{S.ZOOM_START})"
        x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif zoom == "pan_left":
        z = "1.10"
        x, y = f"(iw-iw/zoom)*(1-on/{d})", "(ih-ih/zoom)/2"
    elif zoom == "pan_right":
        z = "1.10"
        x, y = f"(iw-iw/zoom)*(on/{d})", "(ih-ih/zoom)/2"
    else:  # in（默认）
        z = f"min({S.ZOOM_START}+{(S.ZOOM_END - S.ZOOM_START):.3f}*on/{d},{S.ZOOM_END})"
        x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"

    pre = plate_normalize_filter()
    if shot.background == "blur_plate":
        pre += "boxblur=14:2,"
    subtitle = ffmpeg.escape_filter_path(shot.ass)
    fonts = ffmpeg.escape_filter_path(S.FONTS_DIR)
    return (f"{pre}zoompan=z='{z}':x='{x}':y='{y}':d={d}:s={S.WIDTH}x{S.HEIGHT}:fps={S.FPS},"
            f"subtitles={subtitle}:fontsdir={fonts}[v]")


def segment_command(shot: ShotRender, out: Path, *, dry_run: bool = False) -> list[str]:
    frames = max(1, int(round(shot.duration * S.FPS)))
    filter_complex = _video_filter(shot, frames) + f";[1:a]apad,aresample={S.AUDIO_RATE}[a]"
    return [
        S.FFMPEG_BIN, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(shot.plate),
        "-i", str(shot.audio),
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "[a]",
        "-t", f"{shot.duration:.3f}",
        "-c:v", "libx264", "-preset", S.PRESET, "-crf", str(S.CRF),
        "-pix_fmt", "yuv420p", "-r", str(S.FPS),
        "-c:a", "aac", "-b:a", S.AUDIO_BITRATE, "-ar", str(S.AUDIO_RATE), "-ac", "2",
        "-movflags", "+faststart",
        str(out),
    ]


def build_segment(shot: ShotRender, out: Path, *, dry_run: bool = False) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = segment_command(shot, out, dry_run=dry_run)
    if not dry_run:
        ffmpeg.run(cmd, timeout=900)
    shot.segment = out
    return out


def xfade_filter(durations: list[float], fade: float) -> tuple[str, str, float]:
    """构造 xfade + acrossfade 链，返回 (视频滤镜, 音频滤镜, 总时长)。"""
    if len(durations) == 1:
        return "[0:v]null[v]", "[0:a]anull[a]", durations[0]
    video_parts: list[str] = []
    audio_parts: list[str] = []
    prev_v, prev_a = "[0:v]", "[0:a]"
    offset = 0.0
    total = durations[0]
    for index in range(1, len(durations)):
        offset = total - fade
        label_v, label_a = f"[v{index}]", f"[a{index}]"
        video_parts.append(
            f"{prev_v}[{index}:v]xfade=transition=fade:duration={fade}:offset={offset:.3f}{label_v}"
        )
        audio_parts.append(f"{prev_a}[{index}:a]acrossfade=d={fade}{label_a}")
        total = offset + durations[index]
        prev_v, prev_a = label_v, label_a
    return ";".join(video_parts), ";".join(audio_parts), total


def join_commands(segments: list[Path], out: Path, durations: list[float],
                  fade: float = S.FADE_SEC, mode: str = "xfade") -> list[str]:
    inputs: list[str] = []
    for seg in segments:
        inputs += ["-i", str(seg)]
    if mode == "xfade" and len(segments) > 1:
        vf, af, _ = xfade_filter(durations, fade)
        filter_complex = f"{vf};{af}"
        maps = ["-map", "[v]", "-map", "[a]"]
    else:
        stream = "".join(f"[{i}:v][{i}:a]" for i in range(len(segments)))
        filter_complex = f"{stream}concat=n={len(segments)}:v=1:a=1[v][a]"
        maps = ["-map", "[v]", "-map", "[a]"]
    return [
        S.FFMPEG_BIN, "-hide_banner", "-loglevel", "error", "-y",
        *inputs, "-filter_complex", filter_complex, *maps,
        "-c:v", "libx264", "-preset", S.PRESET, "-crf", str(S.CRF),
        "-pix_fmt", "yuv420p", "-r", str(S.FPS),
        "-c:a", "aac", "-b:a", S.AUDIO_BITRATE, "-ar", str(S.AUDIO_RATE), "-ac", "2",
        "-movflags", "+faststart",
        str(out),
    ]


def join_segments(segments: list[Path], out: Path, durations: list[float],
                  fade: float = S.FADE_SEC, *, dry_run: bool = False) -> tuple[Path, str]:
    """按顺序拼接分镜；先用 xfade 交叉淡入，失败时自动回退为硬切（concat）。"""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if dry_run:
        return out, "xfade"
    try:
        ffmpeg.run(join_commands(segments, out, durations, fade, mode="xfade"), timeout=1800)
        return out, "xfade"
    except ffmpeg.FfmpegError:
        ffmpeg.run(join_commands(segments, out, durations, fade, mode="concat"), timeout=1800)
        return out, "concat"


def extract_poster(video: Path, out: Path, at: float = 1.0) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg.run([S.FFMPEG_BIN, "-hide_banner", "-loglevel", "error", "-y",
                "-ss", f"{at:.2f}", "-i", str(video), "-frames:v", "1", "-q:v", "3", str(out)],
               timeout=300)
    return out
