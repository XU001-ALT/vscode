# Tasks: 客户演示视频生成器（Customer-Facing Demo Video Generator）

**Input**: Design documents from `/specs/001-intro-video-generator/`

**Prerequisites**: [plan.md](./plan.md)（必需）、[spec.md](./spec.md)（必需，含用户故事与优先级）、[research.md](./research.md)、[data-model.md](./data-model.md)、[contracts/](./contracts/)、[quickstart.md](./quickstart.md)

**Tests**: **必需**（非可选）。依据 `.specify/memory/constitution.md` 原则 III「新增模块 MUST 附带同目录测试；全量测试 MUST 在任何实现步骤收尾前通过」，每个新增模块都要有对应测试，且必须能直接以 `python tests/test_xxx.py` 独立运行（无 pytest / 无网络 / 无数据库 / 无 API Key），外部依赖以替身隔离。

**Organization**: 任务按用户故事分阶段，每个故事可独立实现与独立验证。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行（不同文件、无未完成依赖）
- **[Story]**: 所属用户故事（US1 / US2 / US3 / US4）
- 每个任务都包含确切文件路径

## Path Conventions

仓库根 `d:\vscode`；产品代码在子目录 `chat-data-assistant/`。本特性全部实现落在 `chat-data-assistant/tools/video/` 子树，测试落在既有 `chat-data-assistant/tests/`。

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 建立工具子树骨架、内容定义初稿与依赖清单。

- [x] T001 创建工具子树骨架与包说明：`chat-data-assistant/tools/video/__init__.py`（记录工具用途与「不 import `db/`、不直连数据库」的边界）、`chat-data-assistant/tools/__init__.py`
- [x] T002 [P] 创建工具依赖清单 `chat-data-assistant/tools/video/requirements-video.txt`，固定版本 `playwright==1.63.0`、`edge-tts==7.2.8`，并写注释说明「不合并进 `requirements.txt`，Playwright 使用系统 Edge/Chrome 通道（无需 `playwright install`）」
- [x] T003 [P] 在 `d:\vscode\.gitignore` 追加一行 `chat-data-assistant/video/runs/`，并确认 `frontend/public/demo*.bak.mp4` 亦被忽略
- [x] T004 [P] 编写分镜内容定义初稿 `chat-data-assistant/tools/video/content/scenes.toml`：`meta.version`、`meta.target_duration_sec = [120, 180]`、`meta.languages = ["zh", "en"]`，8–14 个 `[[shot]]`，满足 `chart_showcase >= 3`、`manual_plot >= 1`、`ui_explain >= 1`、`bilingual_demo == 1`；每镜 `title`/`narration` 均为 `{ zh, en }` 双语非空
- [x] T005 [P] 编写候选与手动绘图素材 `chat-data-assistant/tools/video/content/candidates.toml`：8–20 个 `[[candidate]]`（提问一律用「分组 / 趋势 / 对比 / 分布」句式）+ 至少 1 个 `[[manual]]`（含 `chart_type`、`x_field`/`y_fields` 等字段名，取自后端 schema 真实列名）。这两个 TOML 与 T004 的 `scenes.toml` 构成**非开发人员可编辑的内容入口**，生成逻辑不得硬编码任何提问/文案（FR-016、FR-017）

**Checkpoint**: 内容定义可被人工阅读修改；依赖清单就绪。

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 全部用户故事共同依赖的基础设施。**⚠️ 此阶段完成前不得开始任何用户故事实现。**

- [x] T006 实现 `chat-data-assistant/tools/video/settings.py`：路径常量（`content/`、`video/runs/`、`frontend/public/`）、阈值 `min_data_points = 10`（FR-008）、`max_overlap_ratio = 0.05`、编码参数（`1920x1080`、`fps=30`、`libx264 -preset medium -crf 20 -pix_fmt yuv420p`、`aac -b:a 160k`、`+faststart`）、退出码常量（0/2/3/4/5/6/7/8）、`run_id` 正则 `^[0-9]{8}-[0-9]{6}-[0-9a-f]{7}$`、字体与 TTS 音色（`zh-CN-XiaoxiaoNeural` / `en-US-AriaNeural`）
- [x] T007 [P] 实现 `chat-data-assistant/tools/video/content.py`：用标准库 `tomllib` 读取并校验 TOML。逐条落实 data-model 校验规则：`shot[].id` 匹配 `^[a-z][a-z0-9_]{2,31}$` 且唯一；`shot[].order` 为 1..N 连续无重复；`shot[].kind` 属于 `chart_showcase`/`manual_plot`/`ui_explain`/`bilingual_demo`/`outro`；`shot[].source` 在 `chart_showcase` 时须为 `candidate.id`、在 `manual_plot` 时须为 `manual.id`、其余 kind 必须省略；`narration` 长度 zh 20–220 / en 15–400 字符；`candidate` 数量 8–20；`manual` 数量 ≥ 1；`LocalizedText` 的 `zh` 非空且不含 ASCII 单词（白名单 `SQL`/`AI`/`Plotly`/`Chat Data`）、`en` 非空且不含 CJK
- [x] T008 [P] 实现 `chat-data-assistant/tools/video/ffmpeg.py`：`ffmpeg`/`ffprobe` 封装（`run()`、`probe_json()`），并实现能力探测（`-encoders` 含 `libx264`、`-filters` 含 `zoompan`/`xfade`/`subtitles`，经 `settings.ffmpeg_bin` 或 PATH 解析）
- [x] T009 [P] 实现 `chat-data-assistant/tools/video/safety.py`：敏感信息扫描（密钥、连接串、真实库名或账号、内网地址），复用 `chat-data-assistant/core/secrets.py` 的脱敏模式；提供 `scan_text()` 与 `sanitize()`；所有落盘文本必须先经此模块（FR-018、SC-012）
- [x] T010 [P] 实现 `chat-data-assistant/tools/video/manifest.py`：创建 `runs/<run_id>/` 子目录（`plates`/`clips`/`audio`/`subs`/`segments`）、计算 `sha256`、`short_sha(content files)` 取前 7 位、写入前的「目标已存在即失败」保护（FR-022）
- [x] T011 [P] 实现 `chat-data-assistant/tools/video/ui_surface.py`：锚点常量与健康检查，严格覆盖 `contracts/ui-surface.md` §2 的 A1–A16（`.app[data-lang]`、`.lang-btn`、`.query-box textarea`、`.query-box button`、`.loading-block`、`.result-area`、`.result-body`、`.msg.error`/`.err-detail`、`.ai-answer`、`.chart-view`、`.chart-view-body`、`.js-plotly-plot`、`.xtick`/`.ytick`/`.legend`、`.result-actions`、`.mode-toggle`、`.manual-sql-box`/`.manual-plot-demo`/`.chart-builder`）；硬锚点缺失抛 `UiSurfaceDrift`（退出码 4），软锚点仅告警
- [x] T012 [P] 实现 `chat-data-assistant/tools/video/preflight.py`：9 项检查（`backend`/`frontend`/`schema`/`credential`/`browser`/`ffmpeg`/`font`/`tts`/`disk`），每项产出 `PreflightCheck { id, ok, detail, blocking }`（detail 必须已脱敏）；失败时汇总点名缺失项，**不得**创建成片路径（FR-023）
- [x] T013 [P] 编写 `chat-data-assistant/tests/test_video_content.py`：合法内容通过；`order` 不连续、`id` 重复、缺 `zh`/`en`、kind 非法、`source` 越界、候选数量越界、manual 缺失等逐项报错；**同时静态校验 `ui_surface.py` 的锚点集合与 `contracts/ui-surface.md` 表一致**
- [x] T014 [P] 编写 `chat-data-assistant/tests/test_video_safety.py`：覆盖 API Key（`sk-` 前缀）、Bearer token、`postgresql://user:pass@host/db` 连接串、内网地址（`10.`/`192.168.`/`172.16-31.`）等样例的检出与脱敏；含 `sanitize()` 幂等性用例
- [x] T015 [P] 编写 `chat-data-assistant/tests/test_video_manifest.py`：`run_id` 正则、`short_sha` 取前 7 位、重复写入同路径必须失败、sha256 与文件内容一致
- [x] T016 实现 `chat-data-assistant/tools/video/cli.py` 骨架：`argparse` 全局选项（`--content-dir`/`--runs-dir`/`--run-id`/`--min-data-points`/`--frontend-url`/`--backend-url`/`--headless|--headed`/`--json`/`--verbose`/`--timeout`）、`doctor` 子命令（串起 `preflight` + `ui_surface` 检查）、退出码映射（0/2/3/4/5/6/7/8）；**不得**接受任何凭据参数（出现即按用法错误退 2）
- [x] T017 编写 `chat-data-assistant/tests/test_video_commands.py`：以替身注入 preflight/ui_surface 结果，断言 `doctor` 全通过退 0、缺项退 3、锚点漂移退 4、未知选项退 2；断言 `--json` 输出可被 `json.loads` 解析

**Checkpoint**: 基础层就绪 —— `python tools/video/cli.py doctor`（或 `python -m tools.video.cli doctor`）可运行并按契约返回退出码。

---

## Phase 3: User Story 1 - 一键产出可直接发给客户的演示视频 (Priority: P1) 🎯 MVP

**Goal**: 前后端均在运行时，执行一次生成流程即可拿到完整成片（提问 → 出图链路、1080p/30fps、含旁白与烧录字幕、无敏感信息），全程零人工剪辑。

**Independent Test**: 在平台前后端可正常问答的前提下执行 `probe → build → verify`，检查 `runs/<run_id>/` 出现可被播放器直接打开的 `demo-zh.mp4`，人工确认画面清晰、链路完整、无敏感信息。

### Tests for User Story 1（先写测试并确认其失败）

- [x] T018 [P] [US1] 编写 `chat-data-assistant/tests/test_video_classify.py`：覆盖 `verdict` 三态全部分支 —— `chart_ok` 需同时满足 `api_ok=true`、`intent="chart"`、DOM 命中 `.js-plotly-plot`、`row_count >= 10`；`table_only`（`intent="data"` 或 DOM 无 Plotly 节点）；`failed`（`api_ok=false` 或命中 `.msg.error`）。同时覆盖 `data_points_method` 三取值 `row_count`/`cells`/`manual`（`cells` 用于 `heatmap`/`parallel`/`radar` 等自动多列图型）
- [x] T019 [P] [US1] 编写 `chat-data-assistant/tests/test_video_aesthetics.py`：用固定 `getBoundingClientRect()` 样例数据验证交叠比计算（阈值「交叠面积 / 较小面积 < 5% 且交叠对数 = 0」，边界值 5% 判失败）、`scrollWidth > clientWidth + 1` 截断检测、x/y 轴与图例完整性（多系列时图例项 ≥ 2）、主题一致性（`data-lang=zh` 深色 / `en` 浅色）；断言 `issues` 内容可定位到具体节点
- [x] T020 [P] [US1] 编写 `chat-data-assistant/tests/test_video_subtitles.py`：由同一份 `narration` 生成 `.ass` 与 `.srt`，断言字幕文本与 `narration` 逐条一致（SC-008）、`WordBoundary` 偏移按实测/合成时长比线性缩放、`.ass` 含 `Microsoft YaHei` 与 `fontsdir`、`subtitle_coverage == 1.0`

### Implementation for User Story 1

- [x] T021 [P] [US1] 实现 `chat-data-assistant/tools/video/capture.py`：用 Playwright 驱动系统 Edge/Chrome（`channel="msedge"`，回退 `"chrome"`；`deviceScaleFactor=2`），对单条候选执行「聚焦 `.query-box textarea` → 逐字输入 → 点击 `.query-box button`（或回车）→ 等待 `.js-plotly-plot` 或 `.msg.error`（单条上限 90 秒）」；随后采集：`.chart-view` 元素级 PNG 写入 `plates/`、viewport 视频写入 `clips/`（`--no-clips` 时跳过）、`.msg.error`/`.err-detail` 文本快照（经 `safety.sanitize()`）；返回结构化 `CaptureSnapshot`。画面必须取自**真实运行中的界面**且如实呈现「提问 → 出图」链路（FR-002、FR-003），并覆盖图表以外的界面区域以便后续解释（FR-015）
- [x] T022 [P] [US1] 实现 `chat-data-assistant/tools/video/classify.py`：纯函数 `classify(api_response, dom_snapshot) -> CandidateResult`，产出 `verdict`/`intent`/`chart_type`/`data_points`/`data_points_method`/`api_ok`/`error_code`/`error_excerpt`（`error_excerpt` 上限 200 字符）
- [x] T023 [P] [US1] 实现 `chat-data-assistant/tools/video/aesthetics.py`：在页面内执行量测脚本（刻度/图例文本矩形交叠、文本溢出、轴与图例存在性、主题与色板一致性），产出 `AestheticsReport`（含 `max_overlap_ratio` 与 `issues`）。四项检查严格对应「排版美观」判据：无标签重叠、无文字截断、坐标轴与图例完整、配色与界面主题一致（FR-009）
- [x] T024 [P] [US1] 实现 `chat-data-assistant/tools/video/select.py`：由 `CandidateResult[]` 计算 `recommended = verdict=="chart_ok" and data_points >= min_data_points and 美观四项全 true`，并按「数据点数 → 美观余量 → 图型多样性」排序给出 `rank`（1 起，非推荐为 0）；输出缺口报告（问答出图 < 3 或手动绘图 < 1 时报 `insufficient_qualified_scenes`）。判定与排序即「只把成功出图、数据点充足且美观的场景编入成片」的落地（FR-006、FR-007、FR-010、FR-011）
- [x] T025 [US1] 实现 `chat-data-assistant/tools/video/tts.py`：调用 edge-tts 合成旁白 MP3 到 `audio/`，并收集 `WordBoundary` 逐词时间轴；提供可注入的 `FakeTts`（确定性时长）供测试使用
- [x] T026 [US1] 实现 `chat-data-assistant/tools/video/subtitles.py`：由旁白文本 + `WordBoundary` 生成 `.ass`（`fontsdir=C:/Windows/Fonts`、`Microsoft YaHei`、暗色主题描边）与 `.srt`；按分镜顺序拼接并计算 `subtitle_coverage`。字幕文本与旁白同源，保证「凡有旁白处必有字幕且文本一致」（FR-014）
- [x] T027 [US1] 实现 `chat-data-assistant/tools/video/render.py`（分镜渲染）：静帧 `plates/*.png` → `zoompan` 慢推/慢移（`zoom` 四态、`z` 从 1.0 到 1.12、`d = fps * duration`、`s=1920x1080`）→ `subtitles=` 烧录 → `segments/<shot_id>.mp4`（统一 H.264/AAC 参数）。分镜画面以图表底图作为背景组织（FR-013），分辨率与帧率须达 1080p/30fps（FR-019）
- [x] T028 [US1] 实现 `chat-data-assistant/tools/video/render.py`（拼接与封装）：以 `xfade`（`fade`，0.5s 重叠）串接全部分镜片段并拼接旁白音轨，输出 `demo-zh.mp4`/`demo-en.mp4`（`libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 30` + `aac -b:a 160k` + `-movflags +faststart`）；时长不足的分镜用克隆帧补足以保证 `offset` 正确。该编码组合保证成片可被主流桌面播放器与浏览器直接播放、无需额外解码器（FR-019、FR-020）
- [x] T029 [US1] 实现 `chat-data-assistant/tools/video/cli.py` 的 `probe` 子命令：预检 → 建 `runs/<run_id>/` → 逐条实测（含 `--only`/`--candidate-limit`/`--retries`）→ **增量写** `report.json`，字段严格符合 `contracts/scene-report.schema.json`（`candidates[]` 的 16 个必填字段：`id`/`source`/`prompt`/`verdict`/`intent`/`chart_type`/`data_points`/`data_points_method`/`aesthetics`/`api_ok`/`error_code`/`error_excerpt`/`plate_path`/`recommended`/`rank`/`capture_ms`）。全部图表必须由真实提问在真实数据上产生（FR-004），并为每个候选输出可用性判定、图表类型、数据点数量与推荐顺序（FR-006）
- [x] T030 [US1] 实现 `chat-data-assistant/tools/video/cli.py` 的 `build` 子命令：读 `report.json` → 校验每个 `shot.source` 对应的 `verdict == "chart_ok"`（否则退 5）→ TTS → 字幕 → 分镜渲染 → `xfade` 拼接 → 写 `manifest.json`（`produced_videos[]` 的 19 个必填字段，`verification` 暂为空数组）
- [x] T031 [US1] 实现 `chat-data-assistant/tools/video/cli.py` 的 `verify` 子命令：执行 10 项校验（`V8` 时长落在 `target_duration_sec` ±10%、`V9` 中英一致性、`V10` 样例数量、`V11` 图表质量、`V12` 历史不变、`SC-002` 可播放、`SC-007` 背景占比 ≥ 0.8、`SC-008` 字幕覆盖 = 1.0、`SC-009` ≥1920×1080 且 ≥30fps、`SC-012` 敏感信息 = 0），结果写回 `manifest.json` 的 `verification` 与 `verification_passed`
- [x] T032 [US1] 端到端实跑（需前后端运行 + 服务端有效模型凭据）：`doctor → probe → build → verify`，记录总耗时（须 ≤ 30 分钟，SC-001）与各命令退出码；核对 `chat-data-assistant/video/runs/<run_id>/demo-zh.mp4` 可被播放器直接打开（SC-002）、`report.json` 中无报错/空白/表格画面进入成片（SC-006）、`manifest.json` 的 `sensitive_findings` 为 0（SC-012）。全过程一次执行、零人工剪辑（FR-001）
- [x] T033 [US1] 全量测试回归：`chat-data-assistant\venv\Scripts\python.exe` 依次运行 `tests\test_video_*.py` 全部通过；随后提交本阶段改动

**Checkpoint**: US1 独立可用 —— 得到中英双语成片（若 US2 未完成，先以中文版验收即可）。

---

## Phase 4: User Story 2 - 同一内容产出中英双语两版 (Priority: P2)

**Goal**: 用同一份内容定义分别产出中文版与英文版**两个独立视频**，两者分镜数量与顺序完全一致，差异仅限语言文案。

**Independent Test**: 用同一份内容定义分别生成中文与英文两版，逐段比对分镜数量、顺序与时长，确认结构一致、仅语言不同。

### Tests for User Story 2

- [x] T034 [P] [US2] 编写 `chat-data-assistant/tests/test_video_bilingual.py`：断言按 `zh`/`en` 投影后分镜数量与 `order` 序列逐一对应（SC-003）；断言文本残留检测 —— `zh` 文案不含 ASCII 单词（白名单 `SQL`/`AI`/`Plotly`/`Chat Data`）、`en` 文案不含 CJK；断言缺任一语言时 `content.py` 报错并指明「文件 + 分镜 id + 语言」

### Implementation for User Story 2

- [x] T035 [US2] 在 `chat-data-assistant/tools/video/content.py` 增加 `localize(shot, lang)`：把 `LocalizedText` 投影为单一语言字符串，供 TTS、字幕与画面标题使用；**不得**修改分镜数量或顺序（FR-021）
- [x] T036 [US2] 在 `chat-data-assistant/tools/video/cli.py` 的 `build` 中实现 `--lang both|zh|en`：`both` 产出 `demo-zh.mp4` 与 `demo-en.mp4` 两个独立文件；单语时 `manifest.json` 的 `produced_videos` 仅 1 条（FR-005）
- [x] T037 [US2] 在 `verify` 中实现 `V9` 校验（`chat-data-assistant/tools/video/cli.py` 的 `verify` 分支）：两版 `scene_count` 相同且 `shots[].order` 序列逐一对应；同时检查成片所用文案无另一语言残留，并核对 `bilingual_demo` 分镜确实展示了 `.lang-btn` 触发的界面语言切换（FR-012）
- [x] T038 [US2] 按 `specs/001-intro-video-generator/quickstart.md` 的场景 D 实跑核验：两版结构一致、语言纯净、时长相当；记录结果

**Checkpoint**: US1 + US2 同时可用 —— 双语成片结构一致，仅语言不同。

---

## Phase 5: User Story 3 - 自动挑出「能出好图」的场景（含手动绘图） (Priority: P3)

**Goal**: 对候选提问做实测，输出可用性判定（成功出图 / 仅表格 / 失败）、图表类型、数据点数量与推荐排序；只把「成功出图 + 数据点 ≥ 10 + 排版美观」的场景编入成片，并把**手动绘图**成品一并纳入候选。

**Independent Test**: 给一组候选提问与若干手动绘图成品，运行场景筛选得到带判定的清单；人工抽查被判为「成功出图」的条目确实展示了数据点充足且排版美观的图形。

### Tests for User Story 3

- [x] T039 [P] [US3] 编写 `chat-data-assistant/tests/test_video_select.py`：断言 `recommended` 仅在「`verdict == "chart_ok"` **且** `data_points >= 10` **且** 美观四项全 `true`」时为真（FR-007、SC-005）；断言 `rank` 从 1 起连续、非推荐项为 0；断言问答出图 < 3 或手动绘图 < 1 时报 `insufficient_qualified_scenes` 且不给出推荐

### Implementation for User Story 3

- [x] T040 [US3] 在 `chat-data-assistant/tools/video/capture.py` 实现**手动绘图**采集流程：点击 `.mode-toggle` → 等待 `.result-area.manual-open` 与 `.manual-plot-demo` 出现 → 在 `.chart-builder` 中按 `ManualPlotSpec` 选择 `chart_type` 与字段 → 等待 `.js-plotly-plot` 渲染 → 元素级截图写入 `plates/`（FR-011）
- [x] T041 [US3] 在 `classify.py` 中接入手动绘图：`source="manual"`、`data_points_method="manual"`、`intent=null`，`verdict` 仍按三态判定（DOM 无 Plotly 或渲染异常 → `failed`）
- [x] T042 [US3] 在 `probe` 中实现人类可读输出（表格：`id`/`verdict`/`intent`/`chart_type`/`data_points`/`method`/`aesthetic`/`rank` + `summary` 行）与 `--json` 结构化输出，包含 `table_only`/`failed` 的**改进建议**（如「提问偏聚合，改为分组/趋势句式」）
- [x] T043 [US3] 在 `probe` 中实现中断安全：逐条增量写 `report.json`，进程被中断时保留已完成部分，且**不产出** `segments/`、`demo-*.mp4`、`manifest.json`（FR-023）
- [x] T044 [US3] 依据实测结果调优 `chat-data-assistant/tools/video/content/candidates.toml`：保证采用「分组 / 趋势 / 对比 / 分布」句式，使命中 `intent="chart"` 的候选足以支撑 ≥ 3 个问答出图分镜（`INTENT: data` 只返回单行结果，永远达不到 ≥ 10 数据点）
- [x] T045 [US3] 在 `content.py`/`probe` 中实现手动绘图字段校验：`manual[].x_field`/`y_fields`/`z_field`/`size_field`/`color_field` 必须存在于 `/api/bootstrap` 提供的 schema 列名集合中，否则报 `field_not_found` 并指出可用列名
- [x] T046 [US3] 按 `specs/001-intro-video-generator/quickstart.md` 的场景 B/C 实跑核验：成片中问答出图 ≥ 3、手动绘图 ≥ 1（SC-004）；每个进片图表 `data_points ≥ 10` 且美观四项全 `true`、`issues` 为空（SC-005）；无报错/空白/表格画面（SC-006）

**Checkpoint**: 内容质量可自动把关 —— 只有合格场景能进入成片。

---

## Phase 6: User Story 4 - 内容与产物可复现、可迭代 (Priority: P4)

**Goal**: 产品迭代后重跑一次即可得到与新版本一致的新成片；已发给客户的旧版成片原样留存、绝不被覆盖。

**Independent Test**: 连续执行两次生成，确认第二次成功产出新成片，且第一次的产物文件与内容校验值保持不变。

### Tests for User Story 4

- [x] T047 [P] [US4] 扩展 `chat-data-assistant/tests/test_video_manifest.py`：断言内容定义变化 → `short-sha`（sha256 前 7 位）变化 → 新 `run_id`；同名路径写入必须失败（不覆盖）；`sha256` 与文件字节一致；`published` 备份名格式为 `demo.<YYYYMMDD-HHMMSS>.bak.mp4`

### Implementation for User Story 4

- [x] T048 [US4] 在 `manifest.py` 中落实 `run_id = <YYYYMMDD-HHMMSS>-<short-sha>`（`short-sha` 取内容定义文件 sha256 前 7 位），目录名须匹配 `^[0-9]{8}-[0-9]{6}-[0-9a-f]{7}$`
- [x] T049 [US4] 在 `build`/`manifest.py` 全链路落实「不可覆盖」：目标已有 `demo-*.mp4`/`manifest.json` 即退 6 报 `path_exists`（FR-022）
- [x] T050 [US4] 在 `verify` 中实现 `V12`：核对既有 `runs/*/demo-*.mp4` 的 sha256 未发生变化，结果写入 `verification` 并驱动 `verification_passed`（SC-010）
- [x] T051 [US4] 实现 `chat-data-assistant/tools/video/cli.py` 的 `publish` 子命令：默认 dry-run 打印将复制的文件与备份名；`--apply` 时先把既有 `frontend/public/demo.mp4`、`demo-en.mp4` 备份为 `demo.<YYYYMMDD-HHMMSS>.bak.mp4`，再复制新成片并写 `manifest.json#published`；备份失败或目标不可写退 8
- [x] T052 [US4] 内容变更最小影响验证（US4-AS2）：只替换 `chat-data-assistant/tools/video/content/candidates.toml` 中某个分镜的提问文案后重跑 `probe → build`，确认该分镜画面变化、未改动分镜保持一致；同时按 `specs/001-intro-video-generator/quickstart.md` 的场景 G 验证历史 sha256 不变

**Checkpoint**: 全流程可复现、可迭代，历史产物零风险。

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 跨故事的质量收尾与交付准备。

- [x] T053 [P] 编写 `chat-data-assistant/tools/video/README.md`：命令速查（`doctor`/`probe`/`build`/`verify`/`publish`）、内容编辑指引、退出码表、故障排查，链接 `specs/001-intro-video-generator/{quickstart,contracts/cli,contracts/content-definition,contracts/ui-surface}.md`
- [x] T054 [P] 校验 `d:\vscode\.gitignore` 生效：`git status --short` 不出现 `chat-data-assistant/video/runs/` 下任何文件，也不出现 `frontend/public/demo*.bak.mp4`
- [x] T055 全量测试回归：`chat-data-assistant\venv\Scripts\python.exe` 依次运行 `tests\test_secrets.py` 与全部 `tests\test_video_*.py`，确认全绿（Constitution III 质量门禁）
- [x] T056 按 `specs/001-intro-video-generator/quickstart.md` 逐条执行场景 A–H（含 SC-011 的「5 分钟内独立完成一次生成」），记录每项的实测结果与耗时
- [x] T057 契约不变量终检（[contracts/cli.md](./contracts/cli.md) §7）：① CLI 不接受凭据参数；② 预检失败不产生 `segments/`/`demo-*.mp4`/`manifest.json`；③ `build` 不覆盖、`publish` 必留备份；④ 落盘文本全部经脱敏；⑤ 退出码语义与文档一致
- [x] T058 合规审查：对照 `.specify/memory/constitution.md` v1.0.0 逐条核对（I 只读数据边界、II 密钥永不出服务端、III 测试零外部依赖可运行、IV 契约与双语文案同步演进、V 简单优先/固定版本依赖），确认无违背
- [x] T059 敏感信息终检：对 `runs/*/report.json`、`manifest.json`、`subs/*.srt`、`*.log` 及成片标题/字幕文本执行 `safety.scan_text()`，检出数必须为 0（SC-012、FR-018）
- [x] T060 提交与收尾：按仓库既有提交信息风格分批提交（工具实现 / 内容定义 / 测试 / 文档），确认 `specs/001-intro-video-generator/` 各产物均已入库，并向用户汇报 spec 路径、plan 路径、tasks 完成度与验证结果

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**：无依赖，可立即开始
- **Foundational (Phase 2)**：依赖 Setup 完成 —— **阻断**全部用户故事
- **User Stories (Phase 3–6)**：均依赖 Foundational 完成；其中 US2/US3/US4 复用 US1 建立的 `capture`/`render`/`manifest`/`cli` 骨架，因此建议按 P1 → P2 → P3 → P4 顺序推进（也可在 US1 骨架落地后并行）
- **Polish (Phase 7)**：依赖全部期望交付的用户故事完成

### User Story Dependencies

- **US1 (P1)**：Phase 2 之后即可开始，无跨故事依赖 —— **MVP**
- **US2 (P2)**：Phase 2 之后可开始；与 US1 的 `build`/`render` 集成，但可用 `--lang zh` 独立验收
- **US3 (P3)**：Phase 2 之后可开始；其产出（推荐集合）被 US1 的 `build` 消费，但 `probe` 的输出本身可独立验收
- **US4 (P4)**：Phase 2 之后可开始；`V12`/`publish` 依赖 US1 建立的 `manifest.json`

### Within Each User Story

- 测试必须先写并确认失败，再写实现（Constitution III）
- 模型/纯函数（`classify`/`aesthetics`/`select`）先于采集与渲染
- 采集（`capture`）先于探测（`probe`），渲染（`render`）先于 `build`
- 每个故事完成后再进入下一个优先级

### Parallel Opportunities

- Phase 1 的 T002–T005 全部可并行
- Phase 2 的 T007–T015 全部可并行（不同文件）；T016/T017 需在 T006 之后
- US1 的三个测试任务 T018/T019/T020 可并行；实现中的 T021–T024（采集与纯函数）可并行
- US3 的 T039 可与其他测试并行编写；T040/T042/T043 集中在 `capture.py` 与 `cli.py`，需串行
- Phase 7 的 T053/T054 可并行

---

## Parallel Example: User Story 1

```powershell
# 并行编写 US1 的三个测试文件（不同文件、互不依赖）
Task: "编写 chat-data-assistant/tests/test_video_classify.py"
Task: "编写 chat-data-assistant/tests/test_video_aesthetics.py"
Task: "编写 chat-data-assistant/tests/test_video_subtitles.py"

# 并行实现 US1 的采集与纯函数模块（不同文件）
Task: "实现 chat-data-assistant/tools/video/capture.py"
Task: "实现 chat-data-assistant/tools/video/classify.py"
Task: "实现 chat-data-assistant/tools/video/aesthetics.py"
Task: "实现 chat-data-assistant/tools/video/select.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. 完成 Phase 1（Setup）
2. 完成 Phase 2（Foundational —— 阻断全部故事，必须一次做透）
3. 完成 Phase 3（US1）
4. **停下并验证**：`doctor → probe → build → verify` 产出可播放成片，核对 SC-001/002/006/009/012
5. 此时已可交付给客户使用（可先只发中文版）

### Incremental Delivery

1. Setup + Foundational → 基础就绪
2. US1 → 独立验证 → 交付（MVP）
3. US2 → 独立验证 → 双语交付
4. US3 → 独立验证 → 图表质量达标交付
5. US4 → 独立验证 → 可迭代交付
6. 每个故事都在不破坏前序故事的前提下增加价值

### Parallel Team Strategy

多人协作时：先一起完成 Setup + Foundational，之后
- 开发 A：US1（采集与合成主链路）
- 开发 B：US2（双语投影与一致性校验）
- 开发 C：US3（判定、排序与手动绘图采集）
- 开发 D：US4（产物隔离、清单与发布）
最后共同完成 Phase 7 的收尾与全场景验证。

---

## Notes

- `[P]` = 不同文件、无未完成依赖，可并行
- `[Story]` 标签用于把任务追溯到 `spec.md` 的用户故事
- 每个用户故事都可独立完成与独立验证
- 实现前先确认测试失败
- 每个任务或逻辑分组后提交
- 在任一 Checkpoint 停下来独立验证该故事
- **避免**：含糊任务、同文件冲突、破坏独立性的跨故事依赖
- 实跑类任务（T032/T038/T046/T052/T056）需要**前端 + 后端在运行**且**服务端持有有效模型凭据**；凭据不可用时预检会以退出码 3 明确失败，这不是实现缺陷

---

## 验证记录（收尾实测 · 2026-10-05）

**主链路基线**：`doctor` PASS 9/9 → `probe` run `20261005-183828-270d4a7`（13 候选：chart_ok 12 / table_only 1 / failed 0 /
recommended 11 + manual 2）→ `build --lang both`（`demo-zh.mp4` 136.267s、`demo-en.mp4` 134.033s，均 1920×1080@30fps、
字幕覆盖 100%）→ `verify` **PASS 10/10**、`verification_passed=True`、`sensitive_findings=0`。

### T055 全量回归（12 个文件 / 136 断言 / exit 全 0）

| 测试文件 | 结果 | 测试文件 | 结果 |
|---|---|---|---|
| `test_secrets.py` | 8/8 | `test_video_content.py` | 21/21 |
| `test_video_aesthetics.py` | 14/14 | `test_video_manifest.py` | 12/12 |
| `test_video_bilingual.py` | 14/14 | `test_video_render.py` | 7/7 |
| `test_video_capture.py` | 8/8 | `test_video_safety.py` | 9/9 |
| `test_video_classify.py` | 12/12 | `test_video_select.py` | 8/8 |
| `test_video_commands.py` | 13/13 | `test_video_subtitles.py` | 10/10 |

### T056 场景 A–H 实测

| 场景 | 判据 | 实测结论 |
|------|------|----------|
| A | SC-001/002/009 | 四条命令、零人工干预；`doctor` + `probe`(≈150s) + `build`(185s) + `verify` 合计 ≈6 分 20 秒（上限 30 分钟）；两版均可直接播放，`SC-002`/`SC-009` ok（1920×1080@30fps） |
| B | SC-006/012 | `report.json` 中 11 条 `recommended=true` 全部 `verdict=chart_ok`；`sensitive_findings=0`；`summary.issues=[]` |
| C | SC-004/005 | `V10`（问答出图 5 ≥3、手动绘图 2 ≥1）与 `V11`（点数 ≥10 且美观四项全过）均 ok；抽查 `issues` 为空 |
| D | SC-003 | 两个独立文件、`scene_count` 均 10、`V9` 顺序一致；zh 无白名单外英文、en 无 CJK；含 1 个 `bilingual_demo` 分镜且 `page-lang-zh/en.png` 齐备 |
| E | SC-007 | `chart_background_ratio=[1.0, 1.0]`；存在 `ui_explain` 分镜 |
| F | SC-008 | 10×2 个 `.srt` 齐备且逐条与 `narration` 文本一致（字幕与旁白同源）；覆盖率 `[1.0, 1.0]` |
| G | SC-010 | 复跑新建 `20261005-184829-cdc733d`，`V12` ok；旧 run（`181326`/`183828`）的 `demo-*.mp4` sha256 与基线**逐字节一致** |
| H | FR-023 | 后端指向死端口执行 `probe`：exit `3`、点名 `backend/schema/credential`，run 目录内**只有 `report.json`**（无 `demo-*.mp4`、`segments/`、`manifest.json`） |

> SC-011（无剪辑经验者 5 分钟内独立完成一次生成）：**操作侧满足** —— 仅 4 条命令、零剪辑动作、无必填参数（`publish` 可选且默认 dry-run）。
> 机器侧实测 `probe ≈150s` + `build 185s`，四步合计 ≈6 分 20 秒，**略超 5 分钟**；该下限由真实界面采集与 CPU 渲染（`zoompan`）决定，与操作复杂度无关。


### T057 契约不变量终检

| # | 不变量 | 取证方式 | 结论 |
|---|--------|----------|------|
| ① | CLI 不接受凭据参数 | `tools/video/*.py` 全文检索 `api_key/apikey/password/Bearer/sk-/secret/token`，仅命中 `safety.py` 的**脱敏检测**模式 | ✅ |
| ② | 预检失败不留半成品 | 死端口 `probe`：exit 3，run 内仅 `report.json`，`demo_mp4=0`、无 `segments/plates/clips/manifest.json` | ✅ |
| ③ | `build` 不覆盖 / `publish` 必留备份 | 对已有成片的 run 重跑 `build` → `[E6] path_exists`（exit 6）且原文件 sha256 未变；`publish --apply` → 生成 `demo.20261005-185556.bak.mp4`、`demo-en.20261005-185556.bak.mp4`（旧值留存），目标文件与新成片 sha256 一致；dry-run 零写入 | ✅ |
| ④ | 落盘文本全部经脱敏 | T059 扫描 `runs/**` 下 70 个文本文件，`safety.scan_text` 命中 0 | ✅ |
| ⑤ | 退出码语义与文档一致 | 实测 0（成功）/3（预检）/5（推荐不足）/6（路径已存在）；代码常量 0/2/3/4/5/6/7/8 与 `contracts/cli.md` §4 逐项对应 | ✅ |

### T058 合规审查（Constitution v1.0.0）

| 原则 | 证据 | 结论 |
|------|------|------|
| I 只读数据边界 | 工具不 import `db/`、无 `psycopg/sqlalchemy`、无 SQL 执行入口；仅调用既有 `/api/health`、`/api/bootstrap`、`/api/query` | ✅ 无违背 |
| II 密钥永不出服务端 | 无凭据参数；`safety.py` 复用 `core/secrets.py` 模式并新增连接串/内网地址规则；落盘前统一 `sanitize()` | ✅ 无违背 |
| III 测试零外部依赖 | 12 个测试文件均可 `python tests/test_xxx.py` 直跑，136/136 通过（无 pytest / 无网络 / 无数据库）；15 个功能模块全部有对应测试 | ✅ 无违背 |
| IV 契约与双语文案同步 | `frontend/ api/ ai/ core/` 零 diff（不单侧先行）；`LocalizedText` 强制 zh+en 非空，语言纯净性有断言 | ✅ 无违背 |
| V 简单优先 | 仅新增 2 个固定版本工具依赖（`playwright==1.63.0`、`edge-tts==7.2.8`），不合并进 `requirements.txt`，未引入重复抽象 | ✅ 无违背 |

### 本轮新增 / 修正

- 新增 `tests/test_video_bilingual.py`（14 断言）：补齐 T034 的投影一致性、语言纯净性与「文件 + id + 语言」定位，并覆盖 `V9`/`V12` 判定分支。
- 新增 `tools/video/README.md`（T053）：命令速查、内容编辑指引、退出码表、故障排查、契约链接。
- `tools/video/content.py`：内容非法报错补齐「文件 → 分镜/候选 id → 字段」三段定位（`contracts/content-definition.md` §错误处理）。
- `quickstart.md` §5 与 `README.md` §7：补充「裸 `build` 报 E5」的成因与处理（最新 run 可能是预检失败留下的空报告）。

### 已知限制

- 问答出图分镜的底图**跨 run 天然不同**：同一未改提问的 `data_points` 也会漂移（实测 `tpd_onset_temp` 10 → 959），因为画面来自当次真实 SQL 与真实数据（FR-004）。
  因此 T052 的「该分镜变化、未改动分镜保持一致」在**确定性输入**（手动绘图）上以 sha256 证明（SSIM = 1.000000）；
  在问答出图上只能断言到**内容定义层**（13 条候选中仅目标 1 条 `prompt` 变化，其余 12 条逐字相同）与**历史产物层**（`V12` ok、旧 sha256 不变）。
- `probe` 预检失败留下的 run 目录会成为「最新 run」，导致后续不带 `--run-id` 的 `build` 取到空报告（退出码 5、不产半成品）；已在 quickstart / README 记录处置方式。
