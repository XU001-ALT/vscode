"""字幕生成：ASS（烧录用）与 SRT（校验用），文本与旁白同源（FR-014）。

时间轴由 edge-tts 的 WordBoundary 总时长按字符数比例分配，并把每条字幕的
起止时间吸附到最近的词边界，避免切词导致的口型/语音错位。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import settings as S
from .tts import WordBoundary

# 中文以句读切分，英文以句读 + 空格切分
_ZH_BREAKS = "。！？；，、,.!?;:"
_EN_BREAKS = ".!?;,"


@dataclass
class Cue:
    start: float
    end: float
    text: str

    def to_srt(self, index: int) -> str:
        return (f"{index}\n{_srt_time(self.start)} --> {_srt_time(self.end)}\n{self.text}\n")


def _srt_time(seconds: float) -> str:
    total = max(0.0, seconds)
    hours, rem = divmod(int(total), 3600)
    minutes, secs = divmod(rem, 60)
    millis = int(round((total - int(total)) * 1000))
    if millis == 1000:
        secs += 1
        millis = 0
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _ass_time(seconds: float) -> str:
    total = max(0.0, seconds)
    hours, rem = divmod(int(total), 3600)
    minutes, secs = divmod(rem, 60)
    centis = int(round((total - int(total)) * 100))
    if centis == 100:
        secs += 1
        centis = 0
    return f"{hours:d}:{minutes:02d}:{secs:02d}.{centis:02d}"


def split_cues(text: str, lang: str, max_chars: int | None = None) -> list[str]:
    """把旁白切成屏幕友好的短句（中文约 24 字，英文约 60 字符）。"""
    limit = max_chars or (24 if lang == "zh" else 58)
    breaks = _ZH_BREAKS if lang == "zh" else _EN_BREAKS
    normalized = " ".join(text.split()) if lang == "en" else text.strip()
    cues: list[str] = []
    current = ""
    for ch in normalized:
        current += ch
        is_break = ch in breaks or (lang == "en" and ch == " " and len(current) >= limit * 0.6)
        if is_break and len(current.strip()) >= 6:
            cues.append(current.strip())
            current = ""
        elif len(current) >= limit:
            cues.append(current.strip())
            current = ""
    if current.strip():
        cues.append(current.strip())
    return [c for c in cues if c]


def _snap(value: float, words: list[WordBoundary], *, forward: bool) -> float:
    """把时间吸附到最近的词边界（forward=True 取不早于 value 的词起点）。"""
    if not words:
        return value
    if forward:
        for w in words:
            if w.start >= value:
                return w.start
        return words[-1].end
    for w in reversed(words):
        if w.end <= value:
            return w.end
    return 0.0


def assign_times(cues: list[str], words: list[WordBoundary], duration: float) -> list[Cue]:
    """按字符占比分配时间并吸附到词边界；保证单调、首尾覆盖整段音频。"""
    if not cues:
        return []
    total_chars = sum(len(c) for c in cues) or 1
    span = duration or (words[-1].end if words else len(cues) * 2.0)
    result: list[Cue] = []
    cursor = 0.0
    for index, cue in enumerate(cues):
        share = span * len(cue) / total_chars
        start = cursor
        end = span if index == len(cues) - 1 else cursor + share
        start_snapped = _snap(start, words, forward=True) if index > 0 else 0.0
        end_snapped = _snap(end, words, forward=True) if index < len(cues) - 1 else span
        start_snapped = max(start_snapped, result[-1].end if result else 0.0)
        end_snapped = max(end_snapped, start_snapped + 0.6)
        result.append(Cue(round(start_snapped, 3), round(end_snapped, 3), cue))
        cursor = end
    if words:
        result[-1].end = round(max(result[-1].end, words[-1].end, duration), 3)
    return result


def build_srt(cues: list[Cue]) -> str:
    return "\n".join(cue.to_srt(i) for i, cue in enumerate(cues, start=1))


ASS_HEADER = """[Script Info]
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Demo,{font},{size},&H00FFFFFF,&H000000FF,&H00101828,&H80000000,0,0,0,0,100,100,0,0,1,{outline},1,2,90,90,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def build_ass(cues: list[Cue], *, font: str | None = None, size: int = 46,
              outline: int = 2, margin_v: int = 58,
              width: int | None = None, height: int | None = None) -> str:
    head = ASS_HEADER.format(font=font or S.FONT_NAME, size=size, outline=outline,
                             margin_v=margin_v, width=width or S.WIDTH, height=height or S.HEIGHT)
    lines = [
        f"Dialogue: 0,{_ass_time(c.start)},{_ass_time(c.end)},Demo,,0,0,0,,{c.text}"
        for c in cues
    ]
    return head + "\n".join(lines) + "\n"


def coverage(cues: list[Cue], duration: float) -> float:
    """字幕覆盖旁白时长比（SC-008 要求 1.0）。"""
    if duration <= 0 or not cues:
        return 0.0
    covered = sum(max(0.0, c.end - c.start) for c in cues)
    return round(min(1.0, covered / duration), 4)


def build_shot_subtitles(text: str, lang: str, words: list[WordBoundary], duration: float) -> list[Cue]:
    return assign_times(split_cues(text, lang), words, duration)


def write_subtitles(cues: list[Cue], ass_path: Path, srt_path: Path, **ass_kwargs) -> None:
    Path(ass_path).parent.mkdir(parents=True, exist_ok=True)
    Path(ass_path).write_text(build_ass(cues, **ass_kwargs), encoding="utf-8")
    Path(srt_path).write_text(build_srt(cues), encoding="utf-8")
