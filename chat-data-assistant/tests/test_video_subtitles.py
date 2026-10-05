"""tools.video.subtitles + tts 单元测试：字幕与旁白同源、时间轴与覆盖度（FR-014 / SC-008）。

无 pytest 依赖，可直接运行：
    venv\\Scripts\\python.exe tests\\test_video_subtitles.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.video import subtitles, tts  # noqa: E402

ZH_TEXT = "对比全部 PCT 测试的平台压力与放氢容量分布。系统自动生成查询，并在真实数据上绘制图表，每一个点都是一次真实测试。"
EN_TEXT = "Compare plateau pressure against capacity across all PCT tests. The system writes the query and plots it on real data."


def test_split_cues_zh_splits_on_punctuation():
    cues = subtitles.split_cues(ZH_TEXT, "zh")
    assert len(cues) >= 2
    assert all(len(c) <= 30 for c in cues)
    assert "".join(cues).replace(" ", "") == ZH_TEXT.replace(" ", "")


def test_split_cues_en_stays_readable():
    cues = subtitles.split_cues(EN_TEXT, "en")
    assert len(cues) >= 2
    assert all(c.strip() for c in cues)


def test_assign_times_monotonic_and_covers_duration():
    cues_text = subtitles.split_cues(ZH_TEXT, "zh")
    fake = tts.FakeTts().synthesize(ZH_TEXT, "zh-CN-XiaoxiaoNeural")
    cues = subtitles.assign_times(cues_text, fake.words, fake.duration)
    assert len(cues) == len(cues_text)
    for prev, cur in zip(cues, cues[1:]):
        assert cur.start >= prev.end - 1e-6
    assert cues[0].start == 0.0
    assert abs(cues[-1].end - fake.duration) < 0.05


def test_coverage_is_full():
    fake = tts.FakeTts().synthesize(ZH_TEXT, "zh-CN-XiaoxiaoNeural")
    cues = subtitles.build_shot_subtitles(ZH_TEXT, "zh", fake.words, fake.duration)
    assert subtitles.coverage(cues, fake.duration) == 1.0


def test_cue_text_matches_narration_exactly():
    """字幕文本必须与旁白同源（SC-008），不做任何改写。"""
    fake = tts.FakeTts().synthesize(EN_TEXT, "en-US-AriaNeural")
    cues = subtitles.build_shot_subtitles(EN_TEXT, "en", fake.words, fake.duration)
    joined = "".join(c.text for c in cues)
    assert joined.replace(" ", "") == EN_TEXT.replace(" ", "")


def test_build_ass_has_font_and_events():
    fake = tts.FakeTts().synthesize(ZH_TEXT, "zh-CN-XiaoxiaoNeural")
    cues = subtitles.build_shot_subtitles(ZH_TEXT, "zh", fake.words, fake.duration)
    ass = subtitles.build_ass(cues)
    assert "[V4+ Styles]" in ass and "Microsoft YaHei" in ass
    assert ass.count("Dialogue:") == len(cues)
    assert "PlayResX: 1920" in ass


def test_build_srt_timecodes_are_sorted():
    fake = tts.FakeTts().synthesize(ZH_TEXT, "zh-CN-XiaoxiaoNeural")
    cues = subtitles.build_shot_subtitles(ZH_TEXT, "zh", fake.words, fake.duration)
    srt = subtitles.build_srt(cues)
    stamps = [line for line in srt.splitlines() if "-->" in line]
    assert len(stamps) == len(cues)
    assert stamps[0].startswith("00:00:00,")


def test_write_subtitles_creates_both_files():
    fake = tts.FakeTts().synthesize(ZH_TEXT, "zh-CN-XiaoxiaoNeural")
    cues = subtitles.build_shot_subtitles(ZH_TEXT, "zh", fake.words, fake.duration)
    with tempfile.TemporaryDirectory() as raw:
        ass = Path(raw) / "a.ass"
        srt = Path(raw) / "a.srt"
        subtitles.write_subtitles(cues, ass, srt)
        assert ass.is_file() and srt.is_file()
        assert ass.read_text(encoding="utf-8").count("Dialogue:") == len(cues)


def test_fake_tts_is_deterministic():
    a = tts.FakeTts().synthesize("abc", "v")
    b = tts.FakeTts().synthesize("abc", "v")
    assert a.duration == b.duration and a.audio == b.audio
    assert a.ok and a.words[-1].end > 0


def test_empty_text_yields_no_cues():
    assert subtitles.split_cues("", "zh") == []
    assert subtitles.coverage([], 10.0) == 0.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
