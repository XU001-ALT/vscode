# Data Model: 客户演示视频生成器

**Feature**: `001-intro-video-generator` | **Date**: 2026-10-05 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

本文件定义本特性涉及的全部数据实体、字段、校验规则与状态流转。所有实体都以「文件」形式落地（本特性不写数据库），因此每个实体同时给出**磁盘位置**。字段命名：Python 侧 `snake_case`，JSON 产物（`report.json` / `manifest.json`）与之一致，TOML 内容定义用 `snake_case`。

## 实体总览

| 实体 | 中文名 | 载体 | 进 git | 主要产出阶段 |
|------|--------|------|--------|--------------|
| `ContentDefinition` | 内容定义 | `tools/video/content/*.toml` | 是 | 人工编辑（FR-016/017） |
| `Shot` | 分镜 | `scenes.toml` 的 `[[shot]]` | 是 | 内容定义 |
| `CandidatePrompt` | 候选提问 | `candidates.toml` 的 `[[candidate]]` | 是（不含实测结果） | 内容定义 |
| `ManualPlotSpec` | 手动绘图素材 | `candidates.toml` 的 `[[manual]]` | 是 | 内容定义 |
| `LocalizedText` | 双语文本 | 内联结构 | 是 | 内容定义 |
| `PreflightCheck` | 前置检查项 | `report.json#preflight[]` | 否 | preflight |
| `AestheticsReport` | 美观判定 | `report.json#candidates[].aesthetics` | 否 | probe |
| `CandidateResult` | 候选实测结果 | `report.json#candidates[]` | 否 | probe |
| `SceneReport` | 探测报告 | `runs/<run_id>/report.json` | 否 | probe |
| `GraphicAsset` | 图表素材 | `runs/<run_id>/plates|clips/` | 否 | probe / build |
| `ProducedVideo` | 成片 | `runs/<run_id>/demo-<lang>.mp4` | 否 | build |
| `VerificationCheck` | 校验项 | `manifest.json#verification[]` | 否 | verify |
| `RunManifest` | 运行清单 | `runs/<run_id>/manifest.json` | 否 | build / verify |
| `LanguageVariant` | 语言版本 | 枚举 `zh` / `en` | — | 全程 |

## 1. LocalizedText（双语文本）

内容定义中的一切面向观众的文本都必须是双语且同构（FR-021、SC-003 的结构基础）。

| 字段 | 类型 | 必填 | 校验规则 |
|------|------|------|----------|
| `zh` | string | 是 | 去空白后非空；不含 ASCII 字母单词（专有名词白名单：`SQL`、`AI`、`Plotly`、`Chat Data`） |
| `en` | string | 是 | 去空白后非空；不含 CJK 字符（`\u4e00-\u9fff`） |

校验实现于 `content.py::validate_localized_text`，失败时抛 `ContentError` 并指明「文件 + 分镜 id + 语言」。

## 2. ContentDefinition（内容定义）

一个「内容定义」= 1 套分镜（`scenes.toml`）+ 1 组候选提问与手动绘图素材（`candidates.toml`）。两者都只有 `zh`/`en` 两套文案，但**只有一套分镜结构**。

### 2.1 `scenes.toml`

| 字段 | 类型 | 必填 | 校验规则 |
|------|------|------|----------|
| `meta.version` | string | 是 | 语义化版本，如 `"1.0.0"`；变更内容定义时递增 |
| `meta.title` | LocalizedText | 是 | 成片标题（用于报告与文件命名提示） |
| `meta.target_duration_sec` | [int, int] | 是 | 区间，默认 `[120, 180]`；`build` 超出时告警 |
| `meta.languages` | string[] | 是 | 固定 `["zh", "en"]` |
| `shot` | Shot[] | 是 | 长度 8–14；`order` 必须是 1..N 连续无重复 |

### 2.2 `Shot`（分镜）

| 字段 | 类型 | 必填 | 校验规则 |
|------|------|------|----------|
| `id` | string | 是 | `^[a-z][a-z0-9_]{2,31}$`，全局唯一 |
| `order` | int | 是 | 1..N 连续，决定成片顺序 |
| `kind` | enum | 是 | `chart_showcase` / `manual_plot` / `ui_explain` / `bilingual_demo` / `outro` |
| `source` | string \| null | 否 | `kind=chart_showcase` 时必须是 `candidates.toml` 中某个 `candidate.id`；`kind=manual_plot` 时必须是某个 `manual.id`；其他 kind 必须为 `null` 或省略 |
| `title` | LocalizedText | 是 | 画面标题文字（≤ 28 个字符，超长提示） |
| `narration` | LocalizedText | 是 | 旁白文本；长度 20–220 字符（zh）/ 15–400 字符（en），过短或过长告警（影响单镜时长） |
| `subtitle` | LocalizedText | 否 | 省略时由 `narration` 自动切分生成（默认行为） |
| `duration_sec` | float | 否 | 目标时长；省略时由旁白实测时长决定（±20% 内接受） |
| `zoom` | enum | 否 | `in` / `out` / `pan_left` / `pan_right`，默认 `in` |
| `background` | enum | 否 | `plate`（默认，用图表底图）/ `blur_plate`（模糊底图 + 居中卡片） |

**校验的跨字段规则**：

1. `kind=chart_showcase` 的数量 ≥ 3（FR-010、SC-004）。
2. `kind=manual_plot` 的数量 ≥ 1（FR-011、SC-004）。
3. `kind=ui_explain` 至少 1 个，用于解释「图表以外的界面区域」（FR-015）。
4. `kind=bilingual_demo` 恰好 1 个（展示界面语言切换，FR-012）。
5. 所有分镜的 `source` 必须能在 probe 报告中找到 `verdict == "chart_ok"` 的结果（FR-007）；否则 build 阶段报 `source_not_qualified`。
6. 分镜总时长（旁白实测之和）落在 `meta.target_duration_sec` 的 ±10% 内，否则 `verify` 报 `duration_out_of_range`。

### 2.3 `candidates.toml`

| 字段 | 类型 | 必填 | 校验规则 |
|------|------|------|----------|
| `meta.version` | string | 是 | 语义化版本 |
| `candidate` | CandidatePrompt[] | 是 | 8–20 条，`id` 唯一 |
| `manual` | ManualPlotSpec[] | 是 | ≥ 1 条，`id` 唯一 |

#### CandidatePrompt（候选提问 · 内容侧字段）

| 字段 | 类型 | 必填 | 校验规则 |
|------|------|------|----------|
| `id` | string | 是 | `^[a-z][a-z0-9_]{2,31}$`，全局唯一 |
| `prompt` | LocalizedText | 是 | **必须为可视化导向句式**（分组 / 趋势 / 对比 / 分布）；不得仅含「多少 / 总计 / 统计 / 有几个」等聚合词——此类问法会被后端判为 `data` 意图，只返回单行聚合结果（见 research R3） |
| `expect_chart` | bool | 否 | 默认 `true`；显式设为 `false` 表示该条仅作对照（用于观察 data 意图行为） |
| `notes` | string | 否 | 人工备注，仅写入报告 |
| `ai_recommend` | bool | 否 | 默认 `true`；`false` = 采集时取消勾选界面里的「使用 AI 推荐的图表配置」，改用手动选型（FR-016 的人工干预入口） |
| `chart_type` | enum | 否 | 手动指定的图型（同 `ManualPlotSpec.chart_type` 的 12 种）；必须与 `ai_recommend = false` 同时给出，否则判 `content_invalid` |
| `fields` | string[] | 否 | 在该图型的下拉框行里按顺序匹配并选中这些字段列名；必须与 `ai_recommend = false` 同时给出 |

#### ManualPlotSpec（手动绘图素材 · 内容侧字段）

| 字段 | 类型 | 必填 | 校验规则 |
|------|------|------|----------|
| `id` | string | 是 | 同上 |
| `chart_type` | enum | 是 | `bubble`/`scatter3d`/`heatmap`/`parallel`/`box`/`radar`/`line`/`bar`/`scatter`/`pie`/`area`/`histogram`（与 `ChartView.CHART_ORDER` 一致） |
| `x_field` | string | 条件必填 | `heatmap`/`parallel`/`radar` 可省略；其余必填 |
| `y_fields` | string[] | 条件必填 | 除 `heatmap`/`parallel`/`radar`/`pie` 外必填，至少 1 项 |
| `z_field` | string | 条件必填 | 仅 `scatter3d` 必填 |
| `size_field` | string | 条件必填 | 仅 `bubble` 必填 |
| `color_field` | string | 条件必填 | 仅 `bubble` 必填 |
| `title` | LocalizedText | 是 | 画面标题 |
| `notes` | string | 否 | 人工备注 |

## 3. CandidateResult（候选实测结果）

写进 `runs/<run_id>/report.json` 的 `candidates[]`，共 **16 个必填字段**（对应 `contracts/scene-report.schema.json`）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 对应 `candidates.toml` 的 `candidate.id` 或 `manual.id` |
| `source` | enum `query` \| `manual` | 来源：问答出图 / 手动绘图（FR-011 的区分依据） |
| `prompt` | LocalizedText | 回填实际使用的提问（手动绘图为图形标题） |
| `verdict` | enum `chart_ok` \| `table_only` \| `failed` | 三态判定结果（FR-006；规则见 research R2） |
| `intent` | enum `chart` \| `data` \| `chat` \| `null` | 来自接口响应 |
| `chart_type` | string \| null | `recommendation.chart_type` 或手动绘图所选图型 |
| `data_points` | int | 数据点数（FR-008 的核验值） |
| `data_points_method` | enum `row_count` \| `cells` \| `manual` | 计数方式：明细行数 / 行×数值列（热力图等）/ 手动绘图取行数 |
| `aesthetics` | AestheticsReport | 美观判定（FR-009） |
| `api_ok` | bool | `/api/query` 的 `ok` |
| `error_code` | string \| null | 接口 `error_code` 或本地错误码 |
| `error_excerpt` | string \| null | `.msg.error/.err-detail` 文本快照（已脱敏，≤ 200 字符） |
| `plate_path` | string \| null | 相对 `runs/<run_id>/` 的底图路径，如 `plates/trend_monthly.png` |
| `recommended` | bool | 是否进入推荐集合（三项判据全过） |
| `rank` | int | 推荐排序（1 起；非推荐项为 0） |
| `capture_ms` | int | 本条实测耗时（毫秒），用于 SC-001 的 30 分钟预算核算 |

## 4. AestheticsReport（美观判定）

| 字段 | 类型 | 通过条件 |
|------|------|----------|
| `no_label_overlap` | bool | 刻度/图例文本两两交叠面积比 < 5%（`max_overlap_ratio`）且交叠对数 = 0 |
| `no_text_truncation` | bool | 无文本节点 `scrollWidth > clientWidth + 1` 或 `scrollHeight > clientHeight + 1` |
| `axes_legend_complete` | bool | x/y 轴存在且刻度非空；多系列时图例项 ≥ 2 |
| `theme_consistent` | bool | Plotly 背景与 `.app[data-lang]` 主题一致，且色序命中 `ChartView.PALETTE` |
| `max_overlap_ratio` | float | 实测最大交叠比（可核验依据，SC-005） |
| `issues` | string[] | 失败原因列表（空数组 = 全通过），如 `label_overlap:x-axis`, `truncation:.rec-reason` |

**`recommended` 的判定**：`verdict == "chart_ok"` **且** `data_points >= min_data_points` **且** AestheticsReport 四项全 `true`（FR-007、SC-005）。

## 5. PreflightCheck（前置检查项）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | enum | `backend` / `frontend` / `schema` / `credential` / `browser` / `ffmpeg` / `font` / `tts` / `disk`（见 research R9） |
| `ok` | bool | 是否通过 |
| `detail` | string | 实测细节（如 `ffmpeg 9.0.1, libx264=yes, libass=yes`），已脱敏 |
| `blocking` | bool | 是否阻断后续阶段（本特性全部为 `true`） |

## 6. SceneReport（探测报告）

`runs/<run_id>/report.json`，由 `probe` 写出、`build` 读取（唯一的数据接力载体）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string | `"1.0.0"`，对应 `contracts/scene-report.schema.json` |
| `run_id` | string | 目录名，`<YYYYMMDD-HHMMSS>-<short-sha>` |
| `generated_at` | string | ISO-8601（带时区） |
| `tool_versions` | object | `{ "python": ..., "ffmpeg": ..., "playwright": ..., "edge_tts": ... }` |
| `preflight` | PreflightCheck[] | 9 项检查结果 |
| `candidates` | CandidateResult[] | 全部候选结果（含未推荐项） |
| `summary` | object | `{ "total": n, "chart_ok": n, "table_only": n, "failed": n, "recommended": n, "manual_recommended": n }` |
| `seeded_from` | string \| null | 复用历史报告时的来源路径（默认 `null`，本特性不做自动复用） |

## 7. GraphicAsset（图表素材）

| 字段 | 类型 | 说明 |
|------|------|------|
| `kind` | enum `plate` \| `clip` | 静帧底图 / 真实交互片段 |
| `path` | string | 相对 `runs/<run_id>/` 的路径（`plates/*.png`、`clips/*.webm`） |
| `candidate_id` | string | 来源候选（手动绘图同样有 `candidate_id`） |
| `width` / `height` | int | 像素尺寸（plate 为 2 倍密度，如 3000×1800） |
| `sha256` | string | 文件内容校验值（写入清单，供 `verify` 复核） |
| `captured_at` | string | ISO-8601 采集时刻 |

## 8. ProducedVideo（成片）

`runs/<run_id>/demo-zh.mp4`、`demo-en.mp4`（同一份内容定义产出的**两个独立成片**，FR-005），**19 个必填字段**（对应 `contracts/video-manifest.schema.json` 的 `producedVideo`）：

| 字段 | 类型 | 来源 / 说明 |
|------|------|-------------|
| `language` | enum `zh` \| `en` | LanguageVariant |
| `path` | string | 相对 `runs/<run_id>/` |
| `sha256` | string | 文件内容校验值（SC-010 的核验对象） |
| `bytes` | int | 文件大小 |
| `duration_sec` | float | `ffprobe` 实测 |
| `width` / `height` | int | 实测（SC-009：≥ 1920×1080） |
| `fps` | float | 实测（SC-009：≥ 30） |
| `video_codec` | string | 期望 `h264` |
| `audio_codec` | string | 期望 `aac` |
| `pix_fmt` | string | 期望 `yuv420p`（SC-002 的浏览器兼容前提） |
| `container` | string | `mp4`；且含 `+faststart`（moov 在前） |
| `scene_count` | int | 分镜数量（中英必须相等，SC-003） |
| `chart_background_ratio` | float | 图表背景时长占比（SC-007：≥ 0.8） |
| `subtitle_coverage` | float | 字幕覆盖旁白时长比（SC-008：= 1.0） |
| `sensitive_findings` | int | 敏感信息检出数（SC-012：= 0） |
| `created_at` | string | ISO-8601 |
| `run_id` | string | 所属运行 |
| `source_shots` | ShotEntry[] | 逐分镜的时长与素材溯源 |

### ShotEntry（分镜条目，清单内）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 分镜 id |
| `order` | int | 顺序 |
| `start_sec` / `duration_sec` | float | 在成片中的时间位置（由 `xfade` 重叠量推算） |
| `candidate_id` | string \| null | 素材来源候选 |
| `plate_sha256` | string | 所用底图校验值 |
| `narration_chars` | int | 该镜旁白字符数（用于报告可读性） |

## 9. VerificationCheck（校验项）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | enum | 见下方枚举与映射表 |
| `ok` | bool | 是否通过 |
| `detail` | string | 实测值说明（如 `1920x1080 @ 30.000 fps`） |
| `measured` | number \| null | 数值型实测值（便于回归比较） |
| `blocking` | bool | 失败是否阻断（`true` 时整体 `verification_passed=false`） |

本 schema 版本发出的校验项共 10 个：内部质量项 `V8`–`V12` 与规格成功判据 `SC-002`/`SC-007`/`SC-008`/`SC-009`/`SC-012`。其余成功判据的对应关系：

| 规格判据 | 由谁核验 |
|----------|----------|
| SC-001（≤30 分钟、0 人工干预） | CLI 运行期计时与 `report.json#candidates[].capture_ms` 汇总，写入 `manifest.summary_runtime_sec` |
| SC-003（中英分镜数量与顺序一致） | `V9` |
| SC-004（问答出图 ≥3、手动绘图 ≥1） | `V10` |
| SC-005（数据点 ≥10 且美观四项全过） | `V11` |
| SC-006（报错/空白/表格画面为 0） | `V11` 的前置断言（只允许 `verdict=chart_ok` 的候选被引用） |
| SC-010（历史成片校验值不变） | `V12` |
| SC-011（无剪辑经验者 5 分钟内完成） | [quickstart.md](./quickstart.md) 的手工验证场景 |

## 10. RunManifest（运行清单）

`runs/<run_id>/manifest.json`，唯一产物索引：

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string | `"1.0.0"` |
| `run_id` | string | 目录名 |
| `created_at` | string | ISO-8601 |
| `tool_versions` | object | 同 SceneReport |
| `content_sha256` | object | `{ "scenes": ..., "candidates": ... }`（内容定义指纹，用于复现与 `short-sha`） |
| `content_version` | string | `meta.version` 的组合值，如 `scenes=1.0.0,candidates=1.0.0` |
| `source_report_sha256` | string | 所依据的 `report.json` 校验值 |
| `shots` | ShotEntry[] | 逐分镜溯源 |
| `produced_videos` | ProducedVideo[] | 中文、英文各 1 条 |
| `verification` | VerificationCheck[] | 10 项校验 |
| `verification_passed` | bool | 全部 `blocking` 项通过 |
| `sensitive_findings` | int | 敏感扫描检出总数（SC-012） |
| `published` | object \| null | `{ "applied": bool, "targets": [...], "backups": [...] }`；未发布为 `null` |

## 状态流转

```text
[内容定义] --probe--> report.json(preflight 失败则终止，不建成片路径)
                          |
                          v
                 推荐集合(rank>=1) --build--> plates/clips + audio + subs
                          |                       |
                          |                       v
                          |                 segments/*.mp4 --xfade--> demo-<lang>.mp4
                          v                       |
                    manifest.json <---- verify ----+ (sha256 / ffprobe / 字幕覆盖 / 占比)
                          |
                          v
                  published(可选，显式 --apply，先备份既有 frontend/public/demo*.mp4)
```

**不变式（必须始终成立）**：

1. `probe` 未通过预检时，`runs/<run_id>/` 下**不得**存在 `demo-*.mp4`、`segments/`、`manifest.json`（FR-023）。
2. 任何被成片引用的分镜素材，其候选在 `report.json` 中必须 `verdict == "chart_ok"` 且 `recommended == true`（FR-007、SC-006）。
3. `manifest.json` 写入前，其所在目录不得存在同名文件；`publish` 不得覆盖既有 `frontend/public/demo*.mp4` 而不留备份（FR-022、SC-010）。
4. 中英两版的 `shots[].order` 序列必须逐一对应（FR-021、SC-003）。
5. 所有写入磁盘的文本（报告、清单、日志、字幕）必须先经 `safety.py` 脱敏（FR-018、SC-012）。