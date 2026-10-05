"""客户演示视频生成器（离线工具链）。

边界（与 spec 一致）：
- 只经既有 ``POST /api/query`` 驱动真实界面，**不新增 SQL 执行入口**，不 import ``db/``；
- 不接受任何模型 API Key 参数，凭据一律由后端服务端持有；
- 只读内容定义 ``content/*.toml``，运行产物写入 ``video/runs/<run_id>/``。

入口：``python -m tools.video.cli doctor|probe|build|verify|publish``
"""

__all__ = ["cli", "settings", "content", "capture", "classify", "aesthetics", "select",
           "tts", "subtitles", "render", "ffmpeg", "safety", "manifest", "preflight", "ui_surface"]
