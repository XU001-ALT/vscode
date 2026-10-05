"""tools.video.render 单元测试：底图取景归一与滤镜链（只构建命令，不调用 ffmpeg）。

无 pytest 依赖，可直接运行：
    venv\\Scripts\\python.exe tests\\test_video_render.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.video import ffmpeg  # noqa: E402
from tools.video import render  # noqa: E402
from tools.video import settings as S  # noqa: E402


def _shot(**overrides) -> render.ShotRender:
    data = dict(shot_id="s1", language="zh", plate=Path("plates/a.png"),
                audio=Path("a.mp3"), ass=Path("a.ass"), duration=6.0)
    data.update(overrides)
    return render.ShotRender(**data)


def test_plate_is_scaled_proportionally_and_padded_not_stretched():
    """底图必须先等比缩放 + 补边到 16:9，否则 zoompan 会把竖长截图横向拉宽。"""
    chain = render._video_filter(_shot(), frames=180)
    assert "force_original_aspect_ratio=decrease" in chain
    assert f"pad={int(S.WIDTH * 1.25)}:{int(S.HEIGHT * 1.25)}:" in chain
    assert f"color={S.PLATE_PAD_COLOR}" in chain
    assert "boxblur" not in chain
    assert "zoompan=" in chain
    assert f"s={S.WIDTH}x{S.HEIGHT}" in chain


def test_canvas_and_safe_margin_cover_max_zoom():
    chain = render.plate_normalize_filter()
    canvas_w, canvas_h = int(S.WIDTH * 1.25), int(S.HEIGHT * 1.25)
    inner_w = int(round(canvas_w * (1 - 2 * S.PLATE_SAFE_MARGIN)))
    inner_h = int(round(canvas_h * (1 - 2 * S.PLATE_SAFE_MARGIN)))
    assert f"scale={inner_w}:{inner_h}:" in chain
    assert f"pad={canvas_w}:{canvas_h}:" in chain
    # 安全边距 ≥ 最大推镜裁掉的幅度，推镜到 ZOOM_END 时图形与轴标签仍在画面内
    assert S.PLATE_SAFE_MARGIN >= (1 - 1 / S.ZOOM_END) / 2
    assert inner_w / inner_h == canvas_w / canvas_h


def test_blur_plate_background_keeps_blur_and_normalizes_first():
    chain = render._video_filter(_shot(background="blur_plate"), frames=180)
    assert "force_original_aspect_ratio=decrease" in chain
    assert chain.index("pad=") < chain.index("boxblur=14:2") < chain.index("zoompan=")


def test_segment_command_maps_streams_and_encodes():
    cmd = render.segment_command(_shot(), Path("out.mp4"), dry_run=True)
    assert cmd[cmd.index("-map") + 1] == "[v]"
    assert cmd[cmd.index("-map", cmd.index("-map") + 1) + 1] == "[a]"
    assert "libx264" in cmd and "aac" in cmd and "yuv420p" in cmd
    assert str(cmd[cmd.index("-i") + 1]) == str(Path("plates/a.png"))


def test_xfade_filter_offsets_account_for_overlap():
    vf, af, total = render.xfade_filter([6.0, 8.0], fade=0.5)
    assert "offset=5.500" in vf and "acrossfade=d=0.5" in af
    assert abs(total - 13.5) < 1e-9


def test_subtitle_path_is_quoted_and_colon_escaped():
    """ffmpeg 9.0.1 只接受「单引号 + 双反斜杠转义冒号」的绝对路径写法。"""
    escaped = ffmpeg.escape_filter_path(r"C:\Windows\Fonts")
    assert escaped == r"'C\:/Windows/Fonts'", escaped
    ass = ffmpeg.escape_filter_path(Path(r"d:\vscode\a b\subs\zh.ass"))
    assert ass.startswith("'") and ass.endswith("'")
    assert r"\:" in ass                                   # 盘符冒号转义（单个反斜杠）
    assert "\\v" not in ass                               # 反斜杠统一成正斜杠


def test_video_filter_uses_escaped_subtitle_and_font_paths():
    chain = render._video_filter(_shot(), frames=180)
    assert "subtitles='" in chain
    assert ":fontsdir='" in chain


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
