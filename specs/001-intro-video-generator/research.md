# Phase 0 Research: 客户演示视频生成器

**Feature**: `001-intro-video-generator` | **Date**: 2026-10-05 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

本文件把 Technical Context 中的全部未知项收敛为**决策 + 理由 + 备选方案**。所有环境事实均在本机实测确认。

## 实测确认的环境事实

| 事实 | 实测结果 | 影响 |
|------|----------|------|
| 仓库拓扑 | 单一 git 仓库，根 `d:\vscode`；产品代码在 `chat-data-assistant/`（无嵌套仓库）；当前分支 `feat/intro-video-generator` | 特性代码落 `chat-data-assistant/tools/video/`，测试落 `chat-data-assistant/tests/` |
| Python | 系统 3.14.7；`chat-data-assistant\venv` 有 fastapi/openai/plotly，`d:\vscode\.venv` 无 fastapi | 工具依赖装进 `chat-data-assistant\venv`（后端同环境） |
| FFmpeg | `ffmpeg`/`ffprobe` 9.0.1 位于 `D:\ffmpeg\ffmpeg-9.0.1-full_build\bin`；`--enable-libx264 --enable-libass --enable-libfreetype --enable-fontconfig`；`zoompan`/`xfade`/`subtitles`/`drawtext` 过滤器齐备；`libx264`/`aac` 编码器齐备 | 合成链路无需新增二进制 |
| 字体 | `C:\Windows\Fonts\msyh.ttc`（微软雅黑）、`simhei.ttf`、`arial.ttf` 均存在 | 中英字幕可显式指定字体，避免中文方块 |
| 浏览器 | `msedge.exe`（x86 目录）与 `chrome.exe` 均存在 | Playwright 走系统通道，无需下载 ~150MB 冗余浏览器 |
| 演示位 | `frontend/public/demo.mp4`(4.79MB) + `demo-en.mp4`(4.99MB) + 对应 poster；`IntroPanel.tsx` 按语言选择播放 | 新成片与既有基线并列存放，替换须显式且先备份 |
| 前端结构 | React 19 + Vite + TS + `plotly.js-dist-min`；无任何 `data-testid` | 判定只能依赖既有语义 class 名 → 需 `ui-surface` 契约 + 健康检查 |
| 后端契约 | `POST /api/query` 返回 `ok / error_code / error / sql / columns / rows / row_count / recommendation / answer / intent / corrections / session_id`；`POST /api/session` 建会话 | 判定所需字段全部已在既有契约内，无需改后端 |
| 意图语义 | `ai/prompts.py`：`INTENT: chart` = 可视化需求；`INTENT: data` = **必须只返回单行聚合结果**；`INTENT: chat` = 闲聊 | **关键**：只有 chart 意图才可能满足 ≥10 数据点 |
| 既有脱敏 | `core/secrets.py` 提供 `mask_key`、`sanitize_error`（`sk-…`、`Bearer …` 正则） | 敏感扫描直接复用其模式，不另写宽松实现 |
| 测试约定 | `tests/test_secrets.py`：`sys.path.insert` + 末尾 `if __name__ == "__main__"` 汇总 + `sys.exit(1 if failed else 0)` | 新测试沿用同一写法，无 pytest 依赖 |
| 新增依赖版本 | `playwright==1.63.0`（requires_python ≥3.10，支持 3.14）、`edge-tts==7.2.8` | 固定版本，写进 `requirements-video.txt` |

## 决策记录

### R1 — 如何获得「真实界面」画面

**决策**：用 Playwright 驱动**系统已安装**的 Edge/Chrome（`channel="msedge"`/`"chrome"`），对每个候选提问执行「聚焦输入框 → 逐字输入 → `Enter` 提交 → 等待图表渲染完成」，随后取两类画面素材：

1. **静帧底图（plate）**：以图表容器为锚，取一块 **16:9** 的取景框（高度取满容器、横向加宽到 `height × 16/9` 并夹在视口内，必要时回退为元素级截图）。上下文中含周边界面，成片里既不出现大片补边也不丢内容。上下文设 `deviceScaleFactor=2`，得到 2 倍像素密度底图（如 1148×646 CSS → 2296×1292 px），使 `zoompan` 慢推镜头时仍保持锐利。
2. **交互片段（clip）**：对「提交 → 出图」区间录制 viewport 视频（`record_video_dir`），作为成片里真实交互段落的素材。

**理由**：一次驱动同时产出「高清静帧 + 真实交互片段 + 可判定 DOM 快照」，全程脚本化、可重复，满足 FR-001（零人工）与 FR-003（真实界面）。

**备选方案**：桌面录屏（需人工、不可复现）、`--screenshot` 一次性截图（不可交互、无 DOM 几何量测）、伪造静态图（违背 FR-003/FR-004）——均已否决，详见 plan.md 的 Complexity Tracking。

### R2 — 「成功出图」如何判定（双源交叉）

**决策**：每个候选提问采集三份证据并交叉判定（实现于 `classify.py` 纯函数）：

| 证据源 | 具体字段 / 选择器 | 用途 |
|--------|-------------------|------|
| 接口响应 | `POST /api/query` 的 `ok`、`error_code`、`intent`、`row_count`、`columns`、`recommendation.chart_type` | 是否出错、意图类别、数据点数量、AI 推荐图型 |
| 界面 DOM | `.result-body` 内出现 `.chart-view` 且含 Plotly 根节点 `.js-plotly-plot`；`.msg.error` 是否命中 | 界面是否**真的**画出图形（而非表格或报错） |
| 界面文本 | `.msg.error` / `.err-detail` 文本快照 | 失败原因留痕，写入 probe 报告 |

判定规则：

- `chart_ok`：接口 `ok=true` **且** `intent == "chart"` **且** DOM 命中 `.js-plotly-plot` **且** `row_count >= min_data_points`
- `table_only`：接口 `ok=true`，但 `intent != "chart"`，或 DOM 无 Plotly 节点（仅 `.ai-answer` / 单行聚合表 `.data-*`）
- `failed`：接口 `ok=false`，或 DOM 命中 `.msg.error`

**理由**：只看接口会漏掉「接口成功但界面没画出图」；只看 DOM 拿不到数据点数与推荐图型。交叉判定同时满足 FR-006 的输出要求与 SC-006（成片中报错/空白/表格画面为 0）。

### R3 — 如何稳定获得「数据点较多」的图表（关键发现）

**实测发现**：`ai/prompts.py` 的意图约定中，`INTENT: data` 被要求**只返回一行聚合结果**（例如「一共有多少行」），`INTENT: chart` 才是可视化需求。因此：

- 若在 content 中把提问写成「统计/多少/总计」这类问法，后端会判定为 `data`，界面只渲染单行结论（`DataResultView`），`row_count == 1`，**永远不可能达到 ≥10 数据点**，只会被判为 `table_only`。
- 只有写成「按 X 分组/随 X 变化/对比各类 X」这类**可视化导向**的问法，才会命中 `chart` 意图并返回多行明细，才可能满足 FR-008 的默认阈值 10。

**决策**：
1. `candidates.toml` 中的候选提问一律采用「分组/趋势/对比/分布」句式（如「按月统计各产线的氢气纯度均值变化趋势」），使意图落向 `chart`。
2. `min_data_points = 10` 作为**默认阈值**集中在 `settings.py`（FR-008，Assumptions 允许调整），判定时使用 `row_count`。
3. 数据点为 2–9 的场景不进入成片，但在 probe 报告中保留，便于后续调整内容。

**理由**：这是「哪些问题能得到优秀的图」这一诉求的可核验落地方式；把阈值与句式要求显式化，避免实现阶段反复试错。

### R4 — 「排版美观」如何量测

**决策**：在浏览器内做**确定性几何量测**（`aesthetics.py`），不使用主观打分、不引入视觉模型。四项检查对应 FR-009：

| 检查项 | 量测方式 | 通过条件（阈值见 `settings.py`） |
|--------|----------|----------------------------------|
| 无标签重叠 | 取坐标轴刻度文本（`.xtick`/`.ytick` 文本节点）与图例项的**有向**矩形（中心 + 文字自身宽高 + 旋转角；斜排刻度用 `getBBox` 还原去旋转后的宽高），两两求真实交集面积（凸多边形裁剪） | 交叠面积 / 较小面积 < 5%，且交叠对数 = 0 |
| 无文字截断 | HTML 文本节点：`scrollWidth <= clientWidth + 1` 且 `scrollHeight <= clientHeight + 1`；**SVG `<text>`**（Plotly 的刻度、轴标题、图例全部是 SVG 文本，`clientWidth/clientHeight` 在浏览器里返回无意义值）改为比对文字矩形是否越出被测容器边界 | 无任一节点溢出 |
| 坐标轴与图例完整 | 断言存在非空 x/y 轴标题或刻度，且（多系列时）`legend` 容器存在且项数 ≥ 2 | 全部成立 |
| 配色与主题一致 | 读取 `.app` 的 `data-lang` 判定主题（`zh` 深色 / `en` 浅色），比对 Plotly 容器 `paper_bgcolor` 的解析结果与主题期望值（深色取透明/暗底，浅色取透明/白底），并断言色序来自 `ChartView.PALETTE` | 主题匹配且色板命中 |

### R5 — 旁白与字幕如何做到「文本一致」

**决策**：不使用 ASR 反向对齐。用 edge-tts 合成旁白的同时订阅其 `WordBoundary` 事件（含逐词 `offset`/`duration`），据此：

- 旁白音频：`edge-tts` 输出 MP3（中文音色 `zh-CN-XiaoxiaoNeural`，英文 `en-US-AriaNeural`，语速由 `settings.py` 统一为 `+0%`~`+8%`）。
- 字幕：由**同一份旁白文本**按标点与词边界切分，使用 `WordBoundary` 时间戳生成 `.ass`（烧录用，含 CJK 字体 `Microsoft YaHei`，来自 `C:\Windows\Fonts\msyh.ttc`）与 `.srt`（校验用）。
- 时间轴对齐：分镜音频时长以 `ffprobe` 实测为准，`WordBoundary` 偏移按实测/合成比值线性缩放，消除边界截断误差。

**理由**：字幕文本 = 旁白文本（同一来源），SC-008「字幕覆盖率 100% 且文本与旁白一致」在结构上即被保证；无需模型、无需 ASR，可离线单元测试（`test_video_subtitles.py`）。

### R6 — 合成与编码链路

**决策**：全部用系统 FFmpeg 9.0.1，分三步（`render.py` 只构建命令，执行交给 `ffmpeg.py`）：

1. **取景归一（关键）**：底图是界面元素级截图，比例随内容变化（如 `.chart-view` ≈ 590×646 CSS ≈ 0.91），而 `zoompan` 只按 `s=1920x1080` 输出、**不会保持输入比例**——直接把底图送进去会被横向拉宽（图形与文字变形，观感像「没截全」）。因此先等比缩放 + 居中补边到 16:9 画布（补边色 = 界面深色底 `--bg` `#0b1020`），并按推镜幅度预留安全边距（`PLATE_SAFE_MARGIN` ≈ 6%，即 `(1-1/ZOOM_END)/2` 向上取整），保证推镜到最大时也裁不到图形与轴标签。
2. **分镜渲染**：归一后的画布 → `zoompan` 慢推/慢移（`d=<帧数>`、`fps=30`、`s=1920x1080`，缩放系数 `z` 在 1.0→1.12 之间按分镜随机但确定（由 run seed 决定））→ 叠加 `subtitles=xxx.ass`（`fontsdir=C:/Windows/Fonts`）→ 输出中间片段（统一编码参数）。
3. **拼接**：用 `xfade`（`transition=fade`，0.5s 重叠）按顺序串接所有片段；时长不足的分镜先用克隆帧延长，保证 `offset` 正确。
4. **封装**：视频 `libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 30`；音频 `aac -b:a 160k -ar 44100 -ac 2`；`-movflags +faststart`。

**理由**：`yuv420p` + `H.264 High` + `faststart` 覆盖 SC-002（主流播放器与浏览器直接播放）；`-crf 20` 在 1080p 静帧推镜场景下与源图视觉无损；`xfade` 是 FFmpeg 内置且已验证可用。

**备选方案**：用 MoviePy/imageio 等 Python 合成库 → 引入新依赖且底层仍需 FFmpeg，违背 Constitution V。

### R7 — 内容如何外置

**决策**：内容定义为 TOML（`tools/video/content/scenes.toml` 与 `candidates.toml`），用**标准库** `tomllib` 解析（Python ≥3.11，本机 3.14.7）。

**理由**：TOML 可读性好、有注释、天然支持数组表（分镜与候选天然是数组）；`tomllib` 零新增依赖（Constitution V）；中英文案以 `[shot.text] zh=... en=...` 形式并存，结构同构（FR-021）。

**备选方案**：YAML → 需新增依赖；JSON → 不支持注释、人工编辑体验差；Markdown 解析 → 需自造语法。均否。

### R8 — 产物隔离、可追溯与「不覆盖历史」

**决策**：每次运行创建独占目录 `chat-data-assistant/video/runs/<YYYYMMDD-HHMMSS>-<short-sha>/`（`short-sha` 取内容定义文件的 sha256 前 7 位），内部固定子目录与文件：

```
runs/<run_id>/
├── plates/       # 各分镜静帧底图（PNG，2x）
├── clips/        # 真实交互片段（WebM/MKV，来自 Playwright）
├── audio/        # 旁白 MP3（按语言/分镜）
├── subs/         # .ass 与 .srt
├── segments/     # 中间片段（MP4）
├── report.json   # probe 报告（scene-report schema）
├── demo-zh.mp4 / demo-en.mp4
└── manifest.json # 产物清单（video-manifest schema，含 sha256）
```

- `manifest.py` 在写入前检查目标路径是否存在，存在即失败（不覆盖），满足 FR-022/SC-010。
- 发布到 `frontend/public/` 是**独立子命令** `publish`，默认 dry-run，需显式 `--apply`，且发布前把现有 `demo.mp4`/`demo-en.mp4` 备份为 `demo.<时间戳>.bak.mp4`。
- `.gitignore` 追加 `chat-data-assistant/video/runs/`。

**理由**：目录级隔离使「不覆盖历史」成为结构保证而非约定；`manifest.json` 提供 SC-010 的可核验依据（历史成片 sha256 不变）。

### R9 — 前置条件与快速失败

**决策**：`preflight.py` 在**任何采集动作之前**逐项探测并汇总（对应 FR-023 / US1-AS3）：

| 检查 | 方式 | 缺失时 |
|------|------|--------|
| 后端可达 | `GET /api/bootstrap`（或既有健康端点）2xx | 失败并点名 `backend` |
| 前端可达 | `GET http://localhost:5173/` 2xx | 失败并点名 `frontend` |
| schema 就绪 | `/api/bootstrap` 的 `schema.tables` 非空 | 失败并点名 `schema` |
| 模型凭据可用 | 一次最小代价的 `/api/query` 探针（如「列出租户数量」）返回非 `llm_auth` | 失败并点名 `credential`，提示「需在服务端配置可用的模型凭据」 |
| 浏览器 | `msedge.exe` / `chrome.exe` 存在 | 失败并点名 `browser` |
| FFmpeg | `ffmpeg -version`、`ffprobe -version`，且 `-encoders` 含 `libx264`、`-filters` 含 `zoompan/xfade/subtitles` | 失败并点名 `ffmpeg` |
| 字体 | `C:\Windows\Fonts\msyh.ttc`（或 `simhei.ttf`）存在 | 失败并点名 `font` |
| TTS | 尝试 10 秒超时的极小合成 | 失败并点名 `tts` |
| 磁盘 | 目标卷剩余 ≥ 2 GB | 失败并点名 `disk` |

失败时**只写 probe 报告与日志**，不创建成片路径，满足「不得留下半成品」（FR-023、Edge Cases）。全部检查结果写入 `report.json` 的 `preflight` 段。

**理由**：集中式预检让失败原因可定位、可自动化（doctor 子命令），避免在渲染中途失败。

### R10 — 双语结构、时长与「图表背景占比」

**决策**：

- `scenes.toml` 只定义**一套**分镜序列，每个分镜的 `title`/`narration`/`subtitle` 均为 `{ zh, en }`；生成时按语言投影，因此 SC-003（分镜数量与顺序一致度 100%）由结构保证。
- 目标时长 2–3 分钟：默认 10–12 个分镜，单镜 8–18 秒（由旁白音频时长决定，允许 ±20% 拉伸，超出则报 `duration_out_of_range`）。
- 「图表背景占比 ≥ 80%（SC-007）」：所有分镜的画面层都是「图表底图 + 推镜」，其中 ≥ 80% 的分镜直接使用 `chart_ok` 的图表 plate；开场/结尾分镜也优先用图表 plate 作为背景并叠加标题文字，最终由 `verify` 按分镜时长加权核验。

**理由**：把 SC-003/SC-007 转成结构约束 + 可核验度量，而不是事后人工判断。

## 结论

- 「真实界面采集 + 双源判定 + 几何量测 + WordBoundary 字幕 + FFmpeg 合成」这条链路在本机环境（Edge/Chrome、FFmpeg 9.0.1 含 libx264/libass、CJK 字体、playwright 1.63、edge-tts 7.2.8）上完全可行，无需云服务、无需改后端契约、无需新增运行期依赖。
- 唯一的硬约束是**服务端需要一份可用的模型凭据**（预检项 `credential`）；凭据不可用时，probe 与 build 必须在预检阶段失败，而不是产出空图表。
- 待实现阶段验证的两点（不影响设计）：①`INTENT: chart` 在实际提问下的命中率（决定 candidates 的句式调优）；②`row_count` 是否稳定代表可见数据点（散点/气泡按行计，热力图等按单元格计——实现时对 `AUTO_COL_CHARTS` 类型改用 `row_count × 数值列数` 估算，并在报告中标明估算方式）。
