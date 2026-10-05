"""客户演示视频生成器 —— 集中配置。

路径、阈值、编码参数、退出码全部集中在此，便于非开发人员调整内容侧行为
（对应 FR-008 的「数据点较多」阈值可调、FR-017 的内容与逻辑分离）。
"""
from __future__ import annotations

import os
from pathlib import Path

# ── 路径 ────────────────────────────────────────────────────────────────────
VIDEO_DIR = Path(__file__).resolve().parent            # chat-data-assistant/tools/video
TOOLS_DIR = VIDEO_DIR.parent                           # chat-data-assistant/tools
PROJECT_DIR = TOOLS_DIR.parent                         # chat-data-assistant
REPO_ROOT = PROJECT_DIR.parent                         # d:\vscode

CONTENT_DIR = Path(os.environ.get("VIDEO_CONTENT_DIR", VIDEO_DIR / "content"))
RUNS_DIR = Path(os.environ.get("VIDEO_RUNS_DIR", PROJECT_DIR / "video" / "runs"))
PUBLIC_DIR = PROJECT_DIR / "frontend" / "public"

# ── 服务地址 ────────────────────────────────────────────────────────────────
FRONTEND_URL = os.environ.get("VIDEO_FRONTEND_URL", "http://localhost:5173")
BACKEND_URL = os.environ.get("VIDEO_BACKEND_URL", "http://127.0.0.1:8000")

# ── 判定阈值（FR-008 / FR-009 / FR-010 / FR-011）────────────────────────────
MIN_DATA_POINTS = int(os.environ.get("VIDEO_MIN_DATA_POINTS", "10"))
MAX_OVERLAP_RATIO = 0.05          # 标签交叠面积 / 较小面积 必须小于该值
MIN_TICK_COUNT = 2                # 坐标轴刻度数下限
MIN_CHART_SHOTS = 3               # 成片中「问答出图」样例下限
MIN_MANUAL_SHOTS = 1              # 成片中「手动绘图」样例下限

# ── 成片规格（FR-019 / SC-009）──────────────────────────────────────────────
WIDTH, HEIGHT, FPS = 1920, 1080, 30
PRESET, CRF = "medium", 20
AUDIO_BITRATE = "160k"
AUDIO_RATE = 44100
FADE_SEC = 0.5                    # xfade 交叉淡入时长
ZOOM_START, ZOOM_END = 1.0, 1.12
# 底图安全边距：zoompan 推镜到 ZOOM_END 时会裁掉 (1-1/ZOOM_END)/2 ≈ 5.4%/边，
# 底图先缩到画布的 (1-2*margin) 再补边，保证推镜过程中图形与轴标签始终完整（不裁切）。
PLATE_SAFE_MARGIN = float(os.environ.get("VIDEO_PLATE_SAFE_MARGIN", round((1 - 1 / ZOOM_END) / 2 + 0.006, 3)))
# 补边颜色 = 界面深色主题底 --bg（#0b1020），使底图像是落在界面画布上
PLATE_PAD_COLOR = os.environ.get("VIDEO_PLATE_PAD_COLOR", "0x0b1020")
SHOT_MIN_SEC, SHOT_MAX_SEC = 3.0, 30.0
DURATION_TOLERANCE = 0.10         # verify 的时长容差（±10%）
DEFAULT_TARGET_DURATION = (120.0, 180.0)
CHART_BACKGROUND_MIN_RATIO = 0.80  # SC-007

# ── 采集 ────────────────────────────────────────────────────────────────────
PER_QUERY_TIMEOUT_MS = 90_000
RUN_TIMEOUT_SEC = int(os.environ.get("VIDEO_TIMEOUT", "1800"))
DEVICE_SCALE_FACTOR = 2
VIEWPORT = {"width": 1600, "height": 950}
# 先走系统浏览器通道（无需 `playwright install` 下载 ~150MB）
BROWSER_CHANNELS = ("msedge", "chrome", None)

# ── 字体与语音（FR-014）────────────────────────────────────────────────────
FONT_PATH = Path(os.environ.get("VIDEO_FONT", r"C:\Windows\Fonts\msyh.ttc"))
FONT_NAME = "Microsoft YaHei"
FONTS_DIR = os.environ.get("VIDEO_FONTS_DIR", "C:/Windows/Fonts")
TTS_VOICES = {"zh": "zh-CN-XiaoxiaoNeural", "en": "en-US-AriaNeural"}
TTS_RATE = os.environ.get("VIDEO_TTS_RATE", "+8%")

# ── 外部二进制 ──────────────────────────────────────────────────────────────
FFMPEG_BIN = os.environ.get("VIDEO_FFMPEG_BIN", "ffmpeg")
FFPROBE_BIN = os.environ.get("VIDEO_FFPROBE_BIN", "ffprobe")

# ── 正则 / 枚举 ─────────────────────────────────────────────────────────────
RUN_ID_RE = r"^[0-9]{8}-[0-9]{6}-[0-9a-f]{7}$"
ID_RE = r"^[a-z][a-z0-9_]{2,31}$"
LANGUAGES = ("zh", "en")
SHOT_KINDS = ("chart_showcase", "manual_plot", "ui_explain", "bilingual_demo", "outro")
VERDICTS = ("chart_ok", "table_only", "failed")
DATA_POINTS_METHODS = ("row_count", "cells", "manual")
CHART_TYPES = (
    "bubble", "scatter3d", "heatmap", "parallel", "box", "radar",
    "line", "bar", "scatter", "pie", "area", "histogram",
)
# 手动绘图器（frontend/src/components/ManualPlotter.tsx）只提供这 8 种
MANUAL_CHART_TYPES = ("bubble", "scatter3d", "parallel", "heatmap", "box", "radar", "line", "bar")
MANUAL_FIELD_KEYS = ("capacity", "desorptionTemp", "retention", "kinetics", "year", "pressure")
# 自动使用全部数值列的图型：数据点按「行 × 列」估算
MULTI_COL_CHARTS = ("heatmap", "parallel", "radar")

# ── 退出码（contracts/cli.md §4）────────────────────────────────────────────
EXIT_OK = 0
EXIT_USAGE = 2
EXIT_PREFLIGHT = 3
EXIT_UI_SURFACE = 4
EXIT_CONTENT = 5
EXIT_RENDER = 6
EXIT_VERIFY = 7
EXIT_PUBLISH = 8

MIN_FREE_DISK_GB = 2.0
TTS_PROBE_TIMEOUT_SEC = 15

PUBLISH_TARGETS = {"zh": "demo.mp4", "en": "demo-en.mp4"}
POSTER_TARGETS = {"zh": "demo-poster.jpg", "en": "demo-poster-en.jpg"}
