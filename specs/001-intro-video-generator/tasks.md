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

---

## 增量变更（2026-10-07）：增加「吸氢 / PCT 提问出图」环节

**触发**：负责人反馈成片「提问得到图形展示的太少了」——原片只在 s07 讲了「氢容量随平台压力」一处；要求再加几个与吸氢、PCT 有关的提问出图环节，图表仍须「数据点较多 + 图形美观」，其余内容不动，语序若变则同步调整。

**规格同步（先改规格再改实现）**：

- `spec.md` FR-010：「≥3 个问答出图样例」→「≥4 个，且 MUST 覆盖两种以上数据主题（例如 PCT 与吸氢侧的等温吸放氢测试）」；
- `spec.md` SC-004：同步为 ≥4 个（其中吸氢侧主题 ≥1 个）；
- `spec.md` Assumptions：成片时长量级由 2–3 分钟放宽为 2–3.5 分钟（实测 3:30 中 / 3:26 英）。

**实施（全部落在 `remotion-intro/`，即产线成片的新实现，不触碰平台运行时代码）**：

- [x] T101 真实提问采集：`tools/capture_real.py` 新增 `ISO_Q`（等温吸放氢测试激活能 vs 压力，实测 751 行）与 4 个新状态 —— `24-uptake-typed` / `25-uptake-scatter` / `26-fields-typed` / `27-compare-typed`。typed 状态**只打字不提交**：前端提交后会清空输入框，所以「提问那一刻」必须单独采；`26` / `27` 输入的正是产出 06/08/09 图表的那两句原话。
- [x] T102 新增分镜组件 `src/shots/PUptake.tsx`、`PFields.tsx`、`PCompare.tsx`，注册进 `src/Promo.tsx`；`tools/gen_timeline.py` 的 `SHOTS` 放行 `Uptake` / `Fields` / `Compare`。
- [x] T103 `tools/script.json` 插入 s08（吸氢）/ s09（PCT 五字段）/ s10（PCT 工艺类型）三幕台词，中英各 8 句；后续幕 id 顺移（s08→s11、s09→s12、s10→s13、s11→s14），保证音频文件名前缀 `sNN` 唯一。
- [x] T104 `npm run tts` 重录配音并重算 `src/timeline.ts`；删除 12 个因改号而失效的 mp3（无孤儿音频）。
- [x] T105 校验：`tsc --noEmit` 零错误；10 张代表帧静帧人工核对（三幕的提问画面、751 点散点、162 点三维散点与平行坐标、503 点箱线分布，外加既有 s11 / s12 未回归）；`npm run render-zh` / `render-en` 重出母版与网页版。
- [x] T106 文档同步：`remotion-intro/README.md`「叙事结构」改为 14 幕并补三条新问句、目录结构与配音条数更新。

**验收对照**：

| 判据 | 证据 |
|------|------|
| FR-010 / SC-004：≥4 个问答出图且覆盖两种主题 | s07 压力-容量 1000 点（PCT）· s08 激活能-压力 751 点（等温吸放氢）· s09 五字段 162 点（三维散点 → 平行坐标）· s10 工艺类型 503 点（箱线） |
| FR-007 / FR-008：数据点较多 | 逐幕 1000 / 751 / 162×5 / 503，均远超阈值 10 |
| FR-009 / SC-005：排版美观 | 静帧核对：坐标轴、图例、色阶完整，无标签重叠与文字截断（中文版轴标签已取中文别名：测试编号 / 激活能 / 压力） |
| FR-002 / FR-003 / FR-004：真实链路 | 新截图由 `capture_real.py` 直连真实后端采集（真库 + 真实大模型提问），画面问句与图表同源，未使用模拟数据 |
| SC-006：无报错 / 空白 / 纯表格 | 新幕静帧均无错误提示、空白图表或纯表格 |
| FR-021 / SC-003：中英同构 | 三幕中英分镜数量、顺序、时长差一致，仅文案与界面语言不同 |

**本轮成片规格（实测 · 2026-10-07）**：

| 版本 | 时长 | 帧数 | 母版（crf 18） | 网页版（crf 24） |
|------|------|------|----------------|------------------|
| 中文 | 3:30.5（210.45 s） | 6313 | 121,346,992 B | 50,118,952 B |
| 英文 | 3:26.0（206.04 s） | 6181 | 124,873,776 B | 49,663,038 B |

- 帧数与 `src/timeline.ts` 的 `TOTAL_FRAMES`（6313 / 6181）逐帧一致；抽 9 个代表帧（含新三幕的中英各帧 + 既有 s11 回归帧）与渲染前静帧比对，PSNR 35.8–38.4 dB，无空白帧。
- 配音覆盖：新幕 16 条 cue 全部有音频（3.79–6.96 s），字幕文本与 `tools/script.json` 逐字一致（`out/_check/qa_audio.py`）。
- 已装站内：`frontend\public\demo.mp4` / `demo-en.mp4` + `demo-poster{,-en}.jpg`，并 `-Build` 重建 `frontend\dist`；旧文件备份于 `out\site-backup\20261007-155835-*`，旧母版备份于 `out\_check\promo-{zh,en}-prev.mp4`。

**已知限制 / 取舍**：

- 总时长由 2:48.8 / 2:44.5 增至 **3:30.4 / 3:26.0**（超出 `gen_timeline.py` 的 2–3 分钟软提示，属负责人「多展示」的直接后果，软提示保留）。
- 英文界面图表仍为浅色主题：产品侧既有问题（`ChartView.tsx` 以 `lang === 'zh'` 判定深色），新幕与既有英文幕保持一致，未做单侧修饰。
- s09 / s10 的「提问」画面与随后切出的图表来自同一问句的**不同会话**（图表沿用 2026-10-06 采集的 06 / 08 / 09 状态，不重采以免动到既有幕），提交后输入框本就清空，画面之间无矛盾。

---

## 增量变更（2026-10-07 · 第二批）：三个「不点明图型」的提问出图

**触发**：负责人要求再加三段「不点明图型、只说意图」的提问 —— AI 自己判断该用哪种图形类别，
用来展示平台「换一种问法就换一种图」的能力；并明确要求**问句必须以「绘制」这类绘图动词开头**，
否则意图会被判成 chat / 问数，问不出图。

**实施（同样全部落在 `remotion-intro/`）**：

- [x] T201 问法预检：`out/_check/probe_q.py`（一次性探针，直连 `/api/query`，打印 intent / 行列 / 推荐类型 / SQL）
      逐一试措辞，先定死三句能稳定命中目标图型的问法（详见下「选型结论」）。
- [x] T202 `tools/capture_real.py` 新增 `TREND_Q` / `SHARE_Q` / `COMPARE_Q` 与 6 个状态：
      `28-trend-typed` / `29-share-typed` / `30-compare-typed`（只打字不提交）+
      `31-trend-line` / `32-share-pie` / `33-compare-bar`（出图结果）。
- [x] T203 `ask_type()` 升级：旁听 `/api/query` 响应核对 `chart_type` 是否等于期望值（不等就重问，最多 4 次）；
      中文版追加「`columns` 必须是中文别名」校验（AI 勾选时前端不渲染图型下拉，只能这样核）。
- [x] T204 新增分镜组件 `src/shots/AskPlot.tsx`（一个组件三幕复用：打字拍对准输入框 + 脉冲点，
      出图拍分别标注「推荐理由」与「数据规模」），导出 `PTrend` / `PShare` / `PBars`，
      注册进 `src/Promo.tsx` 的 `SHOTS`，并放行 `gen_timeline.py` 的 `Trend` / `Share` / `Bars`。
- [x] T205 `tools/script.json` 在 s10 之后插入 s11（趋势）/ s12（占比）/ s13（对比）三幕，中英各 9 句；
      后续幕 id 顺移（s11→s14、s12→s15、s13→s16、s14→s17），音频前缀 `sNN` 保持唯一。
- [x] T206 `npm run tts` 重录配音并重算 `src/timeline.ts`；删除 10 个因改号而失效的 mp3（无孤儿音频，音频总数 104 = 52 句 × 2 语言）。
- [x] T207 校对：`tsc --noEmit` 零错误；6 个新状态的中英静帧人工核对（提问文字、AI 推荐理由、图表本身、字幕与角标一致）。
- [x] T208 文档同步：`remotion-intro/README.md` 叙事结构改为 17 幕、补三句新问法、目录结构 / 截图与配音条数更新。

**选型结论（都是实测出来的，不是设计约定）**：

| 幕 | 中文问法 | 英文问法 | AI 推荐 | 真实结果 |
|----|----------|----------|---------|----------|
| s11 趋势 | 绘制 PCT 测试平均放氢容量随温度变化的趋势，列名用中文 | plot the trend of average hydrogen capacity against temperature across the PCT tests | `line` | 103 个温度点连成一条曲线（列名 `温度` / `平均放氢容量`） |
| s12 占比 | 绘制 PCT 测试中吸氢与放氢记录各占多少，列名用中文 | plot the proportion of absorption and desorption records in the PCT tests | `pie` | `pct.type` 两个取值 46.7% / 53.3% |
| s13 对比 | 绘制 PCT 测试每 50 K 温度区间的平均放氢容量对比，哪个区间最高？列名用中文 | plot average hydrogen capacity per 50 K temperature range and show which range is highest | `bar` | 10 档（550~600 K 最高） |

- **直方图问不出来（本轮实测结论，已在 README 记录）**：AI 遇到「分布 / 集中在哪些区间」会在 SQL 里
  先分箱（返回「区间 + 计数」两列），于是稳定推荐 `bar`；若强调「逐条原始值、不要分组」，
  问数模式的安全策略会直接以 `intent=chat` 拒绝并给出改写建议。因此第二版三幕选了折线 / 饼 / 柱。
- 不带绘图动词时（例如「按工艺类型统计…占比」）意图会被判成 data / chat，问不出图；加「绘制」后稳定为 chart。
- 英文版同一句换成英文提问时，`chart_type` 与中文版一致（`line` / `pie` / `bar`），但列名是原始英文列名 —— 与英文版既有幕一致。

**验收对照**：

| 判据 | 证据 |
|------|------|
| 三幕都不点明图型且 AI 各自推荐不同图形类别 | `line` / `pie` / `bar` 三种，均为旁听到的真实 `/api/query` 响应 |
| 问句含绘图动词、意图稳定命中 chart | 三句都以「绘制」开头，中英各一次命中（`ask_type` 日志为 `AI 推荐[1/4]`） |
| FR-004：真实链路 | 6 个状态由 `capture_real.py` 直连真实后端采集，问句与图表同源 |
| SC-006：无报错 / 空白 / 纯表格 | 6 张静帧人工核对通过（折线 103 点、饼图 2 片、柱状 10 档） |
| FR-021 / SC-003：中英同构 | 三幕中英分镜数量、顺序一致，仅文案与界面语言不同 |

> 注：本批「问题里不出现任何图型词」的叙述已被第三批取代（见下），三句问法最终以**句尾点名图型**呈现。

---

## 增量变更（2026-10-07 · 第三批）：三句提问改为「句尾点名图型」

**触发**：负责人追加要求 —— 「提问后面可以明确一下要生成哪种图」。即把 s11–s13 的问法从「只说意图、
选型交给 AI」改成「说清意图 + 句尾点名图型」，解说词、画面标注、屏幕上的问句与配音全部同步改。

**实施（仍全部落在 `remotion-intro/`）**：

- [x] T209 新问法预检（`out/_check/probe_q.py`，zh + en 各 4 条）：点名后三句仍**一次命中**
      `line` / `pie` / `bar`；另加测「点名直方图」—— 中文问法仍推荐 `bar`（AI 先把容量分成 15 个
      0.5 区间再出「区间 + 计数」），英文问法退化成 `scatter`（`bin_start` × `bin_end` 两个数值列），
      结论：**直方图点名也问不出来**，三幕继续用折线 / 饼 / 柱。
- [x] T210 `tools/capture_real.py`：三句问法改为「…，用折线图 / 用饼图 / 用柱状图，列名用中文」（英文对应
      `as a line / pie / bar chart`）；`ask_type()` 新增 `expect_rows` 校验（饼图固定 2 行 —— 否则大模型会
      用 `CASE … ELSE '未知'` 多分出一类，与「两类记录各占多少」的标注不符），注释与文档串同步。
- [x] T211 重采 zh + en 的六个状态（28/29/30 打字中，31/32/33 出图后）：
      zh `line` 103 行 × 2 列（温度 / 平均放氢容量）、`pie` **2 行 × 2 列**（类型 / 记录数）、`bar` 10 行 × 2 列；
      en `line` 103 × 2、`pie` 2 × 2、`bar` 10 × 3（x 轴取区间下限 `temp_range_low`，同样 10 根柱）；
      六次全部 `AI 推荐[1/4]`（第一次就对）。
- [x] T212 文案与时间轴：`src/shots/AskPlot.tsx` 的标注改为「点名」口径（ask / reason / data / tag + 注释），
      `tools/script.json` 的 s11–s13 中英各 3 句改写 → `npm run tts` 只重合成 14 句（其余命中
      `tools/.tts-cache.json`）→ `src/timeline.ts` 重算。
- [x] T213 校对与 QA：`tsc --noEmit` 零错误（`out/_check/typecheck_v2.log` ✓）；`out/_check/qa_v2.py` 帧号已按新
      时间轴更新（zh 4153 / 4431 / 4784 / 5159，en 4015 / 4290 / 4668 / 5030，回归帧 2700），出片后自动跑；
      静帧人工复核（问句在框内不溢出、标注与字幕一致、图表无报错/空白，静帧见 `out/_check/still-*.png`）；
      `qa_audio.py` 复核字幕与 `script.json` 逐字一致。
- [x] T214 出片与发布：`npm run render-zh` / `render-en` 已出片（7458 / 7326 帧）；随后因第四批的「空白尾巴」
      bug 又整条重出一次，**最终发布的是重出后的母版**（zh 137.39 MB / en 143.75 MB，见第四批），
      并由后台链执行 `npm run install-site -- -Build` 换掉站内 `demo.mp4` / `demo-en.mp4` 与两张 poster
      （证据：`out/_check/post-render3.txt`、`verify-site.txt`、`rerender-report.txt`、`site-files-final.txt`）。
- [x] T215 文档同步：`README.md` 的叙事结构（s11–s13 行）、`AskPlot.tsx` 目录注释、问法表三行、
      截图/配音条数已更新；成片「时长 / 体积」两行由 `out/_check/finish_report.py` 在出片后按真实文件
      回填（汇总见 `out/_check/final-verify.txt`）。

**第三批最终问法与结果**：

| 幕 | 中文问法（点名段加粗） | 英文问法 | AI 推荐 | 真实结果 |
|----|------------------------|----------|---------|----------|
| s11 趋势 | 绘制 PCT 测试平均放氢容量随温度变化的趋势，**用折线图**，列名用中文 | plot the trend of average hydrogen capacity against temperature across the PCT tests **as a line chart** | `line` | 103 行 × 2 列（温度 / 平均放氢容量） |
| s12 占比 | 绘制 PCT 测试中吸氢与放氢记录各占多少，**用饼图**，列名用中文 | plot the proportion of absorption and desorption records in the PCT tests **as a pie chart** | `pie` | 2 行 × 2 列（类型 / 记录数 → 吸氢 46.7% / 放氢 53.3%） |
| s13 对比 | 绘制 PCT 测试每 50 K 温度区间的平均放氢容量对比，**用柱状图**，哪个区间最高？列名用中文 | plot average hydrogen capacity per 50 K temperature range **as a bar chart** and show which range is highest | `bar` | 10 根柱（zh 轴为「温度区间」，en 轴为区间下限，550~600 K 最高） |

- 时长随改词变长：zh 由 6313 帧（3:30.4）增至 **7458 帧（4:08.6）**、en 由 6181 帧（3:26.0）增至
  **7326 帧（4:04.2）**；`gen_timeline.py` 的 2–3 分钟软提示继续保留（超出提示仍在，未放宽门禁）。
- 与页面自身提示自洽：站内输入区提示语正是「想绘图时可注明图表类型（如"用折线图展示温度随时间的变化"）」，
  三句问法采用的即这种写法。

**验收对照（第三批）**：

| 判据 | 证据 |
|------|------|
| 三句问法句尾点名图型，且屏幕上的问句与解说词一致 | 静帧里输入框文字 = `TREND_Q` / `SHARE_Q` / `COMPARE_Q`；字幕逐字来自 `script.json` |
| 点名的图型就是画出来的图型 | `/api/query` 响应 `chart_type` 为 `line` / `pie` / `bar`，与响应同名状态截图一致 |
| 饼图确实只有两类 | `expect_rows=2` 校验生效，中英各拿到 2 行（46.7% / 53.3%），无第三类 |
| 中英同构 | 三幕中英分镜数量、顺序一致（各 3 句），仅语言与界面主题不同 |
| 回归无破坏 | 老场景帧（2700）与既有幕静帧 PSNR 通过；`tsc --noEmit` 零错误 |


## 增量变更（2026-10-07 · 第四批）：修掉「每幕最后一句台词期间界面全透明」

**触发**：负责人复看成品时发现 s10–s13 / s16 每幕的**最后一句点题台词**期间整块网页界面全透明 ——
屏幕上只剩背景网格与字幕（中文版合计 ≈19 s、英文版 ≈22 s）。画面里的数据本身没问题（都由真实链路采的），
是**渲染层 bug**。

**根因**：`AskPlot` / `PCompare` / `PUptake` / `PManualPlot` 原先用 `idx = min(画面数 - 1, 拍序)` 取
`start / end`。当一幕的**台词句数多于该分镜的画面数**时（例：s11–s13 各三句台词，却只有「打字 / 出图」
两张画面），`end = bounds[idx + 1]` 已落在当前帧之前 → `leave` 插值恒为 0 → `opacity = enter × leave = 0`，
于是第三句台词期间那张画面死透。

**修复**：四个分镜改为 `start = bounds[idx]`、`end = bounds[beat + 1]` —— **拍序（第几句台词）与画面
（显示哪张截图）分开算**，出场时间取本拍真实结束时刻；`PFields` / `PGallery` 的台词句数与画面数相等，
未改（两处都补了注释说明为什么必须这样取）。

**实施**：

- [x] T216 改 `src/shots/AskPlot.tsx` / `PCompare.tsx` / `PUptake.tsx` / `PManualPlot.tsx`；`npm run typecheck` 零错误。
- [x] T217 新增回归脚本 `out/_check/qa_visible.py`：取每句台词的中点帧，量「网页界面框」区域的最亮像素
      （crop 1456x820@232,78 → 64x36 灰度）——**空白恒为 42、真实内容 ≥67**，阈值 55；对未修的母版可精确
      报出这 10 处（10 BAD）。
- [x] T218 新增 `out/_check/qa_dense.py`：在上一次出片报出的 5 个空白窗口里**逐帧**扫，防「只有中点帧
      正常」的漏网（母版 + 网页版各跑一遍）。
- [x] T219 整条重出两版母版与网页版（`out/_check/chain7_rerender.ps1` → `post_chain7.ps1`），
      时长与帧数**未变**（没裁内容）；随后 `npm run install-site -- -Build` 换站内文件与两张 poster。
- [x] T220 文档同步：`remotion-intro/README.md`「已知坑」补该 bug 的现象 / 根因 / 修法与两个回归脚本；
      `out/_check/review-notes.md` 记新旧对照与证据清单。

**本轮成片规格（实测 · 2026-10-07，内容未裁剪）**：

| 版本 | 时长 | 帧数 | 母版（crf 18） | 网页版（crf 24） | 站内文件 sha256（前 12 位） |
|------|------|------|----------------|------------------|-----------------------------|
| 中文 | 4:08.6（248.619 s） | 7458 | 137.4 MB | 57.0 MB | `A40B59227F94` |
| 英文 | 4:04.2（244.203 s） | 7326 | 143.8 MB | 57.5 MB | `55B951DD979E` |

- 重出耗时：zh 13.9 min（17:37→17:51）、en 14.2 min（17:51→18:05）；两版编码参数未动
  （母版 crf 18、网页版 crf 24 + faststart）。
- 站内一致性：`out/promo-{zh,en}-web.mp4` = `frontend/public/demo{,-en}.mp4` = `frontend/dist/demo{,-en}.mp4`
  三处逐字节相同（sha256 对比，`out/_check/site-files-final.txt`）。

**验收对照（第四批）**：

| 判据 | 证据 |
|------|------|
| 每句台词期间界面都可见 | `qa_visible.py`：修复前 10 BAD → 修复后 **0 BAD**（`qa-visible-before.txt` / `qa-visible-after.txt`，报告尾行 `空白幕数: 0`） |
| 原空白窗口内无漏网帧 | `qa_dense.py`：zh 5 窗口 230 采样最低 83、en 5 窗口 122 采样最低 192（空白为 42），**0 帧**低于阈值；网页版复测同样 0（`qa-dense-after.txt` / `qa-dense-web.txt`） |
| 未回归 | `qa_v2.py` 10/10 OK，PSNR 34.79–37.06 dB，基线拍 2700 / 4153 / 4015 与修复前一致（`post-chain7-report.txt`） |
| 配音与字幕未受影响 | `qa_audio.py` problems = 0（`qa-audio-after.log`） |
| 站内就是本轮母版的网页版 | 三处 sha256 相同（见上表） |

- 旧 QA 为什么漏判：`qa_v2.py` 的参考静帧是**用有 bug 的代码**渲的，参考帧自己就是空白（screen-box 峰值
  全为 42），于是「像不像」永远通过；这批静帧已归档到 `out/_check/blank-stills-archive/`（6 张）。
- 人工复核素材：`out/_check/verify-zh-fixed-spots.mp4`（29.6 s）/ `verify-en-fixed-spots.mp4`（32.0 s）
  —— 把 10 处修复点拼成分段带标注的合辑，`selfcheck_verify_clips.py` 自检 10/10 OK。

**已知限制 / 取舍**：

- 母版与网页版体积较上一版略增（zh 127.8 MiB → 137.4 MB，en 143.8 MB）：修好后多出来的帧现在都是有画面的
  内容帧，编码参数未放宽。
- 英文界面图表仍是浅色主题（`ChartView.tsx` 以 `lang === 'zh'` 判定深色）：产品侧既有问题，本轮不动。
- 站内旧文件已备份到 `out/site-backup/20261007-180537-*`（上一版 `demo.mp4` 53.35 MB / `demo-en.mp4`
  53.28 MB + 两张 poster）；母版与 `out/` 不进 git（`.git/info/exclude`），随版本入库的是
  `frontend/public/demo{,-en}.mp4` 与两张 poster。
- 本轮遗留：`out/_check/chain7_rerender.ps1` 的历史报告里把 `Get-FileHash`（默认 SHA256）标成了 `sha1=`，
  已在该脚本里更正为 `sha256=`；本轮之前的报告文件保留原样，不改写历史证据。



