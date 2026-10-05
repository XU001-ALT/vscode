"""旁白合成与时间轴（FR-014 / research R5）。

用 edge-tts 生成 MP3，同时收集 ``WordBoundary`` 逐词时间戳；
字幕文本与旁白同源，因此「字幕与旁白一致」在结构上即被保证。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import settings as S

try:
    import edge_tts
except Exception:  # noqa: BLE001 - 未安装时仍可 import（测试用 FakeTts）
    edge_tts = None


class TtsError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


@dataclass
class WordBoundary:
    text: str
    start: float          # 秒
    end: float            # 秒


@dataclass
class TtsResult:
    audio: bytes
    words: list[WordBoundary] = field(default_factory=list)
    duration: float = 0.0
    voice: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.audio) and self.duration > 0


async def synthesize(text: str, voice: str, rate: str | None = None,
                     pitch: str | None = None) -> TtsResult:
    """真正的 edge-tts 合成（异步）。offset/duration 单位为 100 纳秒。"""
    if edge_tts is None:
        raise TtsError("tts_missing", "未安装 edge-tts：请执行 `pip install -r tools/video/requirements-video.txt`")
    kwargs = {"rate": rate or S.TTS_RATE}
    if pitch:
        kwargs["pitch"] = pitch
    communicate = edge_tts.Communicate(text, voice, **kwargs)
    buffer = bytearray()
    words: list[WordBoundary] = []
    async for chunk in communicate.stream():
        kind = chunk.get("type")
        if kind == "audio":
            buffer.extend(chunk.get("data") or b"")
        elif kind == "WordBoundary":
            start = float(chunk.get("offset") or 0) / 1e7
            duration = float(chunk.get("duration") or 0) / 1e7
            words.append(WordBoundary(str(chunk.get("text") or ""), start, start + duration))
    duration = words[-1].end if words else 0.0
    if not buffer:
        raise TtsError("tts_empty", f"TTS 未返回音频（voice={voice}, len(text)={len(text)}）")
    return TtsResult(bytes(buffer), words, round(duration, 3), voice)


def _run_synthesis(coro):
    """跑一次合成协程；主线程已有运行中的事件循环时（如 Playwright 同步上下文）改用工作线程。

    ``asyncio.run`` 在已有事件循环的线程里会直接抛 ``RuntimeError``：
    ``build`` 的底图采集（Playwright 同步 API）与 TTS 在同一个线程里发生，
    因此这里必须容忍「已有事件循环」的情况。
    """
    import asyncio
    import threading
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)               # 常规路径：没有运行中的循环
    box: dict[str, object] = {}

    def worker() -> None:
        try:
            box["value"] = asyncio.run(coro)
        except BaseException as exc:           # noqa: BLE001 - 线程内异常需要带回主线程
            box["error"] = exc

    thread = threading.Thread(target=worker, name="video-tts")
    thread.start()
    thread.join()
    if "error" in box:
        raise box["error"]                     # type: ignore[misc]
    return box["value"]


def synthesize_shot(text: str, lang: str, out_path: Path, *, engine=None) -> TtsResult:
    """把一段旁白合成到 ``out_path``（MP3），返回音频与时间轴。"""
    voice = S.TTS_VOICES.get(lang)
    if not voice:
        raise TtsError("tts_voice", f"没有为语言 {lang!r} 配置音色")
    if engine is not None:                     # 测试替身（同步接口）
        result = engine.synthesize(text, voice, rate=S.TTS_RATE)
    else:
        result = _run_synthesis(synthesize(text, voice, rate=S.TTS_RATE))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_bytes(result.audio)
    if not result.audio:
        raise TtsError("tts_empty", f"合成结果为空（lang={lang}, {len(text)} 字符）")
    if result.duration <= 0:
        # 中文等场景下可能收不到 WordBoundary：用 ffprobe 实测 MP3 时长兜底
        from . import ffmpeg
        try:
            result.duration = round(ffmpeg.duration_of(out_path), 3)
        except Exception:                      # noqa: BLE001
            result.duration = round(len(result.audio) / 6000.0, 3)   # 24kHz/48kbps 估算
    if result.duration <= 0:
        raise TtsError("tts_empty", f"无法确定旁白时长（lang={lang}）")
    return result



class FakeTts:
    """确定性替身：无需网络即可跑通整条链路（每字符固定时长）。"""

    def __init__(self, seconds_per_char: float = 0.18):
        self.seconds_per_char = seconds_per_char

    def synthesize(self, text: str, voice: str, rate: str | None = None) -> TtsResult:
        duration = max(1.0, len(text) * self.seconds_per_char)
        words: list[WordBoundary] = []
        cursor = 0.0
        for token in str(text):
            step = duration / max(1, len(text))
            words.append(WordBoundary(token, round(cursor, 3), round(cursor + step, 3)))
            cursor += step
        payload = b"FAKE-MP3" + str(int(duration * 1000)).encode("ascii")
        return TtsResult(audio=payload, words=words, duration=round(duration, 3), voice=voice)
