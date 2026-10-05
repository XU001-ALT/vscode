# Implementation Plan: 客户演示视频生成器（Customer-Facing Demo Video Generator）

**Branch**: `001-intro-video-generator`（git 分支 `feat/intro-video-generator`） | **Date**: 2026-10-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-intro-video-generator/spec.md`

## Summary

**主要需求**：一次执行、零人工剪辑地产出面向客户的中英双语演示成片（1080p/30fps，约 2–3 分钟）。成片以「真实运行界面中的真实图表画面」为背景组织，带旁白与烧录字幕；进入成片的图表必须先经实测筛选（≥3 个问答出图 + ≥1 个手动绘图，每个图表数据点 ≥10 且排版美观）；产物可复现且永不覆盖历史成片。

**技术方案（详见 [research.md](./research.md)）**：

- **画面采集**：用 Playwright（本机已装 Edge/Chrome，走系统浏览器通道）驱动真实前端，在真实后端上回放候选提问；图表区取元素级高清静帧（`deviceScaleFactor=2`）作为背景底图，同时录制「输入问题 → 提交 → 图表渲染」的真实交互片段。
- **可用性判定**：数据面取既有 `POST /api/query` 响应的 `ok` / `intent` / `row_count` / `recommendation.chart_type`；界面面取 DOM 中是否真的渲染出 Plotly 图形节点。二者交叉判定「成功出图 / 仅表格 / 失败」，并给出数据点数与推荐排序。
- **美观判定**：全在浏览器内做确定性几何量测（标签交叠面积、`scrollWidth > clientWidth` 截断、坐标轴与图例完整性、与界面主题配色一致性），阈值集中在 `tools/video/settings.py`。
- **旁白与字幕**：edge-tts 合成中英旁白 MP3，并用同一份旁白文本 + `WordBoundary` 时间轴直接生成 `.ass`（烧录）与 `.srt`（校验），不经 ASR，字幕与旁白文本天然一致。
- **合成与编码**：系统 FFmpeg 9.0.1（已含 libx264 / libass / fontconfig）。静帧用 `zoompan` 做慢推镜头，`subtitles=` 烧录字幕，分镜参数归一后经 `xfade` 拼接，输出 `libx264 -crf 20 -pix_fmt yuv420p` + `aac 160k` + `+faststart` 的 MP4。
- **内容外置**：分镜与候选提问/手动绘图素材放在 `tools/video/content/*.toml`，用 Python 标准库 `tomllib` 读取（零新增解析依赖），工具只读不写；筛选结果另存 `runs/<时间戳>/report.json`。
- **产物隔离**：每次运行独占 `chat-data-assistant/video/runs/<YYYYMMDD-HHMMSS>-<short-sha>/`，`manifest.json` 记录 sha256 与校验结果；发布到前端演示位是独立显式步骤。

## Technical Context

**Language/Version**: Python 3.14.7（项目要求 ≥3.11；`api/compat.py` 负责 typing 兼容）

**Primary Dependencies**:

- 运行期：零新增依赖，仅用标准库 + 复用既有 `core/secrets.py` 的脱敏模式；不 import `db/`、不直连数据库
- 工具期（新增、固定版本，见 Complexity Tracking）：`playwright==1.63.0`、`edge-tts==7.2.8`
- 外部二进制：FFmpeg 9.0.1（`ffmpeg` / `ffprobe`，本机 `D:\ffmpeg\ffmpeg-9.0.1-full_build\bin`，已确认 `--enable-libx264 --enable-libass --enable-fontconfig`）

**Storage**: 文件系统

- 内容定义（进 git）：`chat-data-assistant/tools/video/content/{scenes,candidates}.toml`
- 运行产物（不进 git）：`chat-data-assistant/video/runs/<run_id>/`（plates / clips / audio / subs / segments / 成片 / manifest.json）
- 不写数据库、不写 `data/sessions.sqlite3`

**Testing**: `chat-data-assistant/tests/test_video_*.py`，沿用仓库既有约定：无 pytest、无网络、无数据库、无 API Key，可直接 `venv\Scripts\python.exe tests\test_video_xxx.py` 独立运行（参照 `tests/test_secrets.py` 的 `if __name__ == "__main__"` 汇总与退出码写法）；外部依赖一律以替身隔离（`FakeBrowser` / `FakeTts` / `FakeFfmpeg`）

**Target Platform**: 生成端为本机 Windows（Edge/Chrome 与 FFmpeg 已具备）；成片面向任意桌面播放器与浏览器（H.264 High + AAC-LC + faststart）

**Project Type**: 单仓库（根 `d:\vscode`）+ 产品子目录 `chat-data-assistant/`。本特性是**离线工具链 + CLI**，既不是后端 `/api/*` 接口，也不是前端页面

**Performance Goals**:

- SC-001：单次生成（probe + build + verify）≤ 30 分钟，人工干预 0 次
- 单条候选提问实测 ≤ 90 秒（含页面渲染与截图）
- 成片 1920×1080 / 30fps；`libx264 -preset medium -crf 20`；10 秒分镜渲染约 5–15 秒（zoompan 为 CPU 密集操作）

**Constraints**:

- 前置条件：前端与后端均在运行、schema 就绪、服务端模型凭据可用、TTS 端点可达、磁盘余量充足
- 「数据点较多」默认阈值 `min_data_points = 10`，集中在 `settings.py` 可配置（FR-008）
- 只经既有 `/api/query` 驱动，**不得新增 SQL 执行入口**（Constitution I）
- 不接受任何 API Key 作为参数；产物必须通过敏感信息扫描（Constitution II / FR-018）
- 不修改后端 `/api/*` 契约、不修改前端 `src/api.ts` 与 `src/types.ts`（Constitution IV）
- 中英两版共用同一分镜结构，仅文案不同（FR-021）

**Scale/Scope**: 单机、单用户串行；候选提问 8–20 条、手动绘图素材 ≥1 个；每语言分镜 8–14 个；每次运行产出中英 2 个成片 + 1 份清单

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

依据 `.specify/memory/constitution.md` v1.0.0 的五条原则逐条设闸：

| # | 原则 | 判定 | 依据 / 反证 |
|---|------|------|-------------|
| I | 只读数据边界（NON-NEGOTIABLE） | **PASS** | 本特性不新增 SQL 执行入口：所有查询都经既有 `POST /api/query`（内部仍走 `ai/sql_guard.py` + `ai/text_to_sql.py`）。工具侧不 `import db.*`、不持有数据库连接、不构造 SQL；候选提问是自然语言，交由既有链路生成并校验。 |
| II | 密钥永不出服务端（NON-NEGOTIABLE） | **PASS** | 工具不接受任何 Key 参数，不读写 `core/secrets` 的存储；采集时不触碰密钥输入区；产物经 `safety.py` 复用 `core.secrets.sanitize_error` 的正则模式 + 连接串/内网地址模式扫描；新增 `chat-data-assistant/video/runs/` 到 `.gitignore`。 |
| III | 测试零外部依赖可运行 | **PASS** | 判定规则、美观阈值、字幕生成、敏感扫描、FFmpeg 命令构建、清单与冲突检测全部设计为纯函数；浏览器 / TTS / FFmpeg 以替身注入。`tests/test_video_*.py` 可直接运行且不联网。 |
| IV | 契约与双语文案同步演进 | **PASS** | 不改后端 `/api/*`，不改 `frontend/src/api.ts` 与 `src/types.ts`（工具只消费既有契约）。新增契约集中在 `specs/001-intro-video-generator/contracts/`，其中 `ui-surface.md` 显式声明对前端既有 class 名的依赖与变更协议。内容定义中英同构（差异仅文案）。 |
| V | 简单优先，复用既有技术栈 | **PASS（附 1 项已论证的依赖新增）** | 运行期零新增依赖；内容定义用标准库 `tomllib` 而非新增 YAML 解析；不引入数据库/队列/服务化。工具期新增 2 个依赖（playwright、edge-tts）已固定版本并记录在 Complexity Tracking，隔离在 `tools/video/requirements-video.txt`，不影响 `requirements.txt` 与 Dockerfile。 |

**Phase 0 后复核**：研究结论未引入新的执行入口、密钥路径或前端契约变更，五条闸门结论不变。

**Phase 1 后复核**：设计产物（`data-model.md`、`contracts/*`、`quickstart.md`）未新增 API 路由、未改动既有契约文件、未引入隐式依赖，五条闸门结论不变。**无待证违规项。**

## Project Structure

### Documentation (this feature)

```text
specs/001-intro-video-generator/
├── plan.md              # 本文件（/speckit-plan 输出）
├── research.md          # Phase 0 输出（技术选型与关键发现）
├── data-model.md        # Phase 1 输出（实体、字段、校验规则、状态流转）
├── quickstart.md        # Phase 1 输出（安装、运行、端到端验证场景）
├── contracts/           # Phase 1 输出（接口契约）
│   ├── cli.md                       # CLI 子命令 / 选项 / 退出码契约
│   ├── content-definition.md        # 内容定义（TOML）契约
│   ├── scene-report.schema.json     # probe 报告 JSON Schema
│   ├── video-manifest.schema.json   # 产物清单 JSON Schema
│   └── ui-surface.md                # 界面锚点（依赖的前端 class）契约
├── checklists/
│   └── requirements.md  # 需求质量检查清单（已 16/16 通过）
└── spec.md              # 功能规格（WHAT/WHY）
```

### Source Code (repository root)

仓库根为 `d:\vscode`，产品代码位于其子目录 `chat-data-assistant/`。本特性作为**独立工具子树**落地，不触碰 `api/`、`ai/`、`core/`、`db/`、`frontend/` 的既有行为：

```text
chat-data-assistant/
├── tools/video/                        # 本特性全部实现（离线工具链，非服务端运行时代码）
│   ├── __init__.py
│   ├── cli.py                          # 子命令入口：doctor / probe / build / verify / publish
│   ├── settings.py                     # 路径、阈值（min_data_points=10 等）、编码参数、退出码
│   ├── content.py                      # 读取并校验 content/*.toml（tomllib，只读）
│   ├── preflight.py                    # 前置条件探测（前端/后端/凭据/浏览器/FFmpeg/字体/TTS/磁盘）
│   ├── ui_surface.py                   # UI 锚点契约与健康检查（见 contracts/ui-surface.md）
│   ├── capture.py                      # 驱动真实界面：静帧 plate + 交互录屏 clip + 文本快照
│   ├── classify.py                     # 成功出图 / 仅表格 / 失败 + 图表类型 + 数据点数
│   ├── aesthetics.py                   # 标签重叠 / 文字截断 / 坐标轴图例 / 配色一致性
│   ├── select.py                       # 推荐排序与缺口检测（≥3 问答出图、≥1 手动绘图）
│   ├── tts.py                          # edge-tts 合成 + WordBoundary 时间轴
│   ├── subtitles.py                    # ASS（烧录）/ SRT（校验）生成
│   ├── ffmpeg.py                       # ffmpeg / ffprobe 封装与命令构建
│   ├── render.py                       # 分镜渲染（zoompan + subtitles）+ xfade 拼接 + 混音
│   ├── safety.py                       # 敏感信息扫描（复用 core/secrets 模式）
│   ├── manifest.py                     # run 目录、sha256 清单、不可覆盖校验
│   ├── content/
│   │   ├── scenes.toml                 # 分镜内容定义（中英同构，人工可编辑，进 git）
│   │   └── candidates.toml             # 候选提问 + 手动绘图素材（人工可编辑，进 git）
│   └── requirements-video.txt          # 工具依赖：playwright==1.63.0、edge-tts==7.2.8
├── tests/                              # 仓库既有测试目录（无 pytest、可直接运行）
│   ├── test_secrets.py                 #   既有文件，作为本特性测试写法基线
│   ├── test_video_content.py
│   ├── test_video_classify.py
│   ├── test_video_aesthetics.py
│   ├── test_video_subtitles.py
│   ├── test_video_safety.py
│   ├── test_video_manifest.py
│   └── test_video_commands.py
├── video/runs/<run_id>/                # 运行产物（不进 git）：plates / clips / audio / subs / segments / 成片 / manifest.json
└── frontend/public/demo*.mp4           # 既有演示位：仅由显式 `publish` 子命令更新，且先备份

d:\vscode\.gitignore                    # 追加一行：chat-data-assistant/video/runs/
```

**Structure Decision**：选择「既有单仓库 + 工具子树」结构，而非模板中的单一项目或前后端分离选项。理由：本特性不新增后端路由（不落 `api/routes/`）、不新增前端页面（不落 `frontend/src/`），其全部行为是离线的「采集 → 筛选 → 合成」流水线，因此集中在 `chat-data-assistant/tools/video/` 一个子树内，测试沿用仓库根既有 `tests/` 目录；这样既满足 Constitution III（测试可直接运行），也让本特性的全部改动（除 `.gitignore` 一行与 `frontend/public/` 的显式发布产物外）与产品运行时代码零交叉。

## Complexity Tracking

> 本表仅登记 Constitution Check 中需要额外论证的复杂度。五条原则均判定 PASS，唯一的复杂度增量是工具期新增 2 个第三方依赖（已固定版本并隔离，不影响运行期与部署）。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| 新增依赖 `playwright==1.63.0` | FR-003 要求画面取自**真实运行中的界面**；FR-007/009 要求对「是否真的出图」与排版美观做**可核验**判定；FR-002 要求呈现「提问 → 出图」链路画面。这需要真实浏览器中的「交互 + 元素级量测 + 元素截图 + 过程录屏」四件事同时具备。 | ①FFmpeg `gdigrab` 录屏：需人工操作、不可复现、画质受桌面干扰，违背 FR-001/SC-011 的零人工；②仅用 `msedge --headless --screenshot`：无法交互、无法读取 DOM 几何信息（判定美观）、无法录屏；③用生成的静态图代替真实界面截图：直接违背 FR-003/FR-004。 |
| 新增依赖 `edge-tts==7.2.8` | FR-009/SC-008 要求「凡有旁白处必有字幕且文本与旁白一致」。edge-tts 的 `WordBoundary` 事件给出逐词时间戳，使字幕由**旁白文本本身**生成，文本一致性与时间同步同时得到保证，且免费、可复现、无需服务端凭据。 | ①OpenAI TTS：占用模型额度，且把 Key 暴露面引入生成链路（与 Constitution II 的谨慎方向相反）；②Windows SAPI：中文音色可用性不保证、音质机械化，且需额外做时间轴对齐；③用 ASR 反向对齐：多一个模型依赖，且语音识别误差会破坏「字幕与旁白一致」的硬性要求。 |
