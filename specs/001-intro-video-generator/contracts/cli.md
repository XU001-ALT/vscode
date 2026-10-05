# Contract: CLI（命令行接口契约）

**Feature**: `001-intro-video-generator` | **Version**: 1.0.0 | **Date**: 2026-10-05

本契约定义视频生成工具的命令行接口。该 CLI 是本特性**唯一**对外入口（无 HTTP 接口、无前端入口）。

## 1. 调用方式

```powershell
cd d:\vscode\chat-data-assistant
.\venv\Scripts\python.exe -m tools.video.cli <command> [options]
```

- 建议工作目录为 `chat-data-assistant/`（默认路径基于此解析）；在其他目录运行时会出现「找不到默认路径」错误，除非显式传 `--content-dir` 与 `--runs-dir`。
- 所有子命令**禁止**接受模型 API Key 之类的凭据参数（Constitution II / FR-018）；凭据一律由后端服务端持有。

## 2. 子命令一览

| 子命令 | 作用 | 主要副作用 | 幂等性 |
|--------|------|------------|--------|
| `doctor` | 预检 9 项前置条件 + 界面锚点健康检查 | 无（只读探测） | 是 |
| `probe` | 实测候选提问与手动绘图素材，写 `report.json` | 新建 `runs/<run_id>/`（采集物） | 每次新 `run_id` |
| `build` | 读取 `report.json` 合成中英成片，写 `manifest.json` | 写 `plates/audio/subs/segments/demo-*.mp4` | 同一 `run_id` 重复调用失败（保护） |
| `verify` | 核对成片质量与合规，更新 `manifest.json` 的校验项 | 更新 `manifest.json` | 是 |
| `publish` | 把成片发布到前端演示位（默认 dry-run） | `--apply` 时写 `frontend/public/` 并先备份 | 是（`--apply` 前先 dry-run） |

## 3. 全局选项

| 选项 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `--content-dir PATH` | path | `tools/video/content` | 内容定义目录（含 `scenes.toml`、`candidates.toml`） |
| `--runs-dir PATH` | path | `video/runs` | 运行产物根目录 |
| `--run-id ID` | string | 自动生成 | 沿用既有运行目录（`build`/`verify`/`publish` 常用；不传则用最近一次） |
| `--min-data-points N` | int | `10` | 「数据点较多」阈值（FR-008；覆盖 `settings.py` 默认值） |
| `--frontend-url URL` | string | `http://localhost:5173` | 前端地址 |
| `--backend-url URL` | string | `http://127.0.0.1:8000` | 后端地址 |
| `--headless` / `--headed` | flag | `--headless` | 是否显示浏览器窗口（调试用 `--headed`） |
| `--json` | flag | off | 以 JSON 输出结果摘要（供脚本消费），不输出进度条 |
| `--verbose` | flag | off | 输出调试细节（含 FFmpeg 命令、选择器命中情况） |
| `--timeout SEC` | int | `1800` | 单次整体运行上限（SC-001 的 30 分钟护栏） |

## 4. 退出码

| 码 | 含义 | 触发示例 |
|----|------|----------|
| `0` | 成功 | 全部 `blocking` 校验通过 |
| `2` | 用法错误 | 未知子命令、缺必填参数、`--min-data-points` 非正整数 |
| `3` | 前置条件不满足 | 后端不可达、凭据失效、FFmpeg 缺 libx264（`doctor`/`probe`/`build` 均可能） |
| `4` | 界面锚点漂移 | `ui_surface` 硬锚点缺失（见 [ui-surface.md](./ui-surface.md) §3） |
| `5` | 内容定义非法 | TOML 语法错误、`order` 不连续、中英缺一、分镜数越界、`source` 不存在 |
| `6` | 渲染/编码失败 | FFmpeg 非 0 退出、`zoompan`/`xfade` 滤镜不可用、磁盘写失败 |
| `7` | 校验不通过 | `verify` 存在 `blocking` 项失败（分辨率、占比、字幕覆盖、敏感信息等） |
| `8` | 发布被拒绝 | `publish --apply` 时目标已存在且未通过备份检查，或 `--apply` 未先通过 dry-run |

约定：**任何非 0 退出码都不得留下会被误当成成片的文件**（FR-023）。失败时 `stderr` 输出一行 `[E<code>] <检查项>: <原因>`，`--json` 时同时输出结构化错误对象到 stdout。

## 5. 子命令详情

### 5.1 `doctor`

```powershell
python -m tools.video.cli doctor [--json] [--verbose]
```

- 执行 research R9 的 9 项检查（`backend`/`frontend`/`schema`/`credential`/`browser`/`ffmpeg`/`font`/`tts`/`disk`）+ §ui-surface 锚点健康检查。
- 只读：不创建 `runs/` 目录、不调用除 `GET /api/bootstrap` 与一次最小 `/api/query` 探针之外的接口。
- 输出（示例）：

```text
[ok]   backend      HTTP 200 http://127.0.0.1:8000/api/bootstrap
[ok]   frontend     HTTP 200 http://localhost:5173/
[ok]   schema       tables=7
[ok]   credential   probe query ok=true intent=chart
[ok]   browser      msedge 已找到
[ok]   ffmpeg       ffmpeg 9.0.1 (libx264=yes libass=yes zoompan=yes xfade=yes)
[ok]   font         C:\Windows\Fonts\msyh.ttc
[ok]   tts          zh-CN-XiaoxiaoNeural 1.2s / en-US-AriaNeural 1.1s
[ok]   disk         42.7 GB 可用
[ok]   ui_surface   A1,A3,A4,A7,A10,A11,A12,A15,A16 命中
PASS 10/10
```

- 退出码：全通过 `0`；有失败 `3`；锚点漂移 `4`。

### 5.2 `probe`

```powershell
python -m tools.video.cli probe [--only SUBSTR] [--candidate-limit N] [--retries N] [--no-clips] [--headed] [--json]
```

| 选项 | 默认 | 说明 |
|------|------|------|
| `--only SUBSTR` | — | 只实测 id 含该子串的候选（调试用） |
| `--candidate-limit N` | 全部 | 最多实测 N 条（先按内容定义顺序） |
| `--retries N` | `1` | 单条失败的重试次数（网络抖动容忍） |
| `--no-clips` | off | 不录制交互片段（加快探测；成片不再含真实交互画面） |

行为：先跑预检（失败即退 `3`/`4`）→ 新建 `runs/<run_id>/` → 逐条实测（输入 → 提交 → 等 `.js-plotly-plot` 或 `.msg.error`，最长 90 秒/条）→ 元素级截图写 `plates/` → 量测美观 → 脱敏扫描 → **增量写** `report.json`（中断也保留已完成部分，但不产成片）。

输出（`--json` 关闭时）：

```text
run_id   20261005-142530-a1b2c3d
id                  verdict     intent  chart      points  method  aesthetic  rank
trend_monthly       chart_ok    chart   line       36      rows    pass       1
compare_units       chart_ok    chart   bar        24      rows    pass       2
manual_bubble       chart_ok    manual  bubble     30      manual  pass       3
count_total         table_only  data    -          1       rows    -          0
bad_prompt          failed      -       -          0       -       -          0
summary  total=5 chart_ok=3 table_only=1 failed=1 recommended=3 (manual=1)
```

退出码：成功 `0`（即使存在未推荐项）；无任何 `recommended` 项 → `0` 但输出 `WARN insufficient_qualified_scenes`（由 `build` 拒绝继续）。

### 5.3 `build`

```powershell
python -m tools.video.cli build [--lang both|zh|en] [--dry-run] [--verbose]
```

- 读取 `report.json`；若 `recommended` 中「问答出图 ≥ 3」或「手动绘图 ≥ 1」不满足 → 退出码 `5`，错误 `insufficient_qualified_scenes`（提示修改 `candidates.toml` 或放宽阈值）。
- 校验每个分镜的 `source` 可解析且 `verdict=chart_ok`（否则 `5`）。
- 渲染顺序：分镜 → 旁白 TTS（`audio/`）→ 字幕（`subs/`，`.ass`+`.srt`）→ 分镜片段（`segments/`）→ `xfade` 拼接 → `demo-zh.mp4` / `demo-en.mp4` → `safety` 扫描 → 写 `manifest.json`（不含 verify 结果，`verification` 为空数组）。
- `--dry-run`：只打印将要执行的 FFmpeg 命令与产物路径，不写任何文件。
- 同一 `run_id` 已存在成片 → 退出码 `6`，错误 `path_exists`（FR-022 保护）。

### 5.4 `verify`

```powershell
python -m tools.video.cli verify [--run-id ID] [--strict] [--json]
```

- 对 `manifest.json` 中的每条成片执行 10 项校验（见 [data-model.md](../data-model.md) §9）：

| id | 校验内容 | 通过条件 |
|----|----------|----------|
| `V8` | 时长 | 落在 `scenes.toml` 的 `target_duration_sec` ±10% |
| `V9` | 中英一致性 | 两版 `scene_count` 相同且 `shots[].order` 逐一对应 |
| `V10` | 样例数量 | 问答出图 ≥ 3 且手动绘图 ≥ 1 |
| `V11` | 图表质量 | 引用候选的 `data_points ≥ 10` 且美观四项全 `true` |
| `V12` | 历史不变 | 既有 `runs/*/demo-*.mp4` 的 sha256 与记录一致 |
| `SC-002` | 可播放（FR-020：无需额外解码器） | `ffprobe` 可解析，`h264`+`aac`+`yuv420p`+`faststart` |
| `SC-007` | 背景占比 | `chart_background_ratio ≥ 0.8` |
| `SC-008` | 字幕覆盖 | `subtitle_coverage == 1.0` 且字幕文本与 `narration` 一致 |
| `SC-009` | 分辨率/帧率（FR-019：≥1080p/30fps） | `width ≥ 1920 && height ≥ 1080 && fps ≥ 30` |
| `SC-012` | 敏感信息 | `sensitive_findings == 0`（密钥/连接串/库名账号/内网地址） |

- 结果写回 `manifest.json` 的 `verification` 与 `verification_passed`。
- 退出码：全部 `blocking` 通过 `0`；有失败 `7`；`--strict` 时告警也计为失败。

### 5.5 `publish`

```powershell
python -m tools.video.cli publish [--run-id ID] [--apply] [--target DIR] [--json]
```

- **默认 dry-run**：打印将要复制的文件与将创建的备份名，不改动任何文件。
- `--apply`：先备份既有 `frontend/public/demo.mp4`、`demo-en.mp4`（备份名 `demo.<YYYYMMDD-HHMMSS>.bak.mp4`），再复制新成片与 poster（若产物中存在 `poster-*.jpg`），最后把结果写入 `manifest.json#published`。
- 幂等：重复 `--apply` 会再次备份后再覆盖；已发布的旧文件始终留有备份（SC-010 的「历史留存」在发布层面的延伸）。
- 退出码：成功 `0`；备份失败或目标不可写 `8`。

## 6. 典型调用序列

```powershell
# 日常：一次到位
python -m tools.video.cli doctor
python -m tools.video.cli probe
python -m tools.video.cli build
python -m tools.video.cli verify

# 只重做中文版（沿用既有 report.json）
python -m tools.video.cli build --lang zh --run-id 20261005-142530-a1b2c3d

# 调内容后只测某几条候选
python -m tools.video.cli probe --only trend_

# 发布前先看会发生什么
python -m tools.video.cli publish
python -m tools.video.cli publish --apply
```

## 7. 不变量与失败行为

1. CLI 不接受任何凭据参数；出现 `--api-key` 之类未知选项时按用法错误退 `2`。
2. `probe`/`build` 在预检失败时**不得**创建 `segments/`、`demo-*.mp4`、`manifest.json`。
3. `build` 不覆盖既有产物；`publish` 不覆盖既有演示位而不留备份。
4. 所有落盘文本先脱敏；`--verbose` 也不得打印未脱敏文本。
5. 退出码语义稳定，属于对外契约的一部分，不得随实现细节变动。