# 客户演示视频生成器（tools/video）

用一句自然语言提问，驱动**真实运行中的** chat-data-assistant 界面（提问 → 出图），
把最有说服力的图表自动编成一支 1080p/30fps 的中英双语演示片 —— 全程**零人工剪辑**。

- 内容与画面都可追溯：每个分镜的来源候选、数据点数、美观结论、底图 sha256 都写在 `manifest.json`。
- 只在现实前先探测：`probe` 会实测每一条候选提问，只有「成功出图 + 数据点 ≥ 10 + 排版美观」的场景才能进片。
- 历史成片永不覆盖：每次生成落在独立 `runs/<run_id>/`，`verify` 的 `V12` 会核对历史成片 sha256 未变。

面向人工的完整说明见 [`specs/001-intro-video-generator/quickstart.md`](../../../specs/001-intro-video-generator/quickstart.md)。

## 1. 安装（一次性）

```powershell
cd d:\vscode\chat-data-assistant
.\venv\Scripts\python.exe -m pip install -r tools\video\requirements-video.txt
```

只装两个固定版本的工具依赖（`playwright==1.63.0`、`edge-tts==7.2.8`）；**不合并**进 `requirements.txt`，
不影响产品运行期与 Docker 构建。Playwright 走系统已安装的 Edge/Chrome 通道，**无需** `playwright install`。

## 2. 五分钟跑通

```powershell
cd d:\vscode\chat-data-assistant

# ① 体检：9 项前置条件（不产生任何产物）
.\venv\Scripts\python.exe -m tools.video.cli doctor

# ② 探测：实测全部候选提问，输出判定与推荐排序（新建一个 runs/<run_id>/）
.\venv\Scripts\python.exe -m tools.video.cli probe

# ③ 合成：按推荐分镜产出中英两个成片（默认 --lang both）
.\venv\Scripts\python.exe -m tools.video.cli build

# ④ 校验：分辨率/帧率/时长/字幕覆盖/图表占比/敏感信息（建议显式带 --run-id）
.\venv\Scripts\python.exe -m tools.video.cli verify --run-id <run_id>

# ⑤ 发布（可选）：写入前端演示位；默认 dry-run，需显式 --apply
.\venv\Scripts\python.exe -m tools.video.cli publish --run-id <run_id> --apply
```

前 ①②③ 要求 `启动.bat` 已拉起前后端，且服务端持有**有效的**模型凭据。

## 3. 命令速查

| 命令 | 作用 | 常用参数 |
|------|------|----------|
| `doctor` | 9 项前置检查（`backend`/`frontend`/`schema`/`credential`/`browser`/`ffmpeg`/`font`/`tts`/`disk`），不产生任何产物 | `--json` |
| `probe` | 逐条实测候选提问与手动绘图，写 `report.json`（判定 / 图型 / 数据点数 / 美观 / 推荐排序） | `--only <子串>`、`--candidate-limit N`、`--retries N`、`--no-clips`、`--api-cross-check`、`--headed` |
| `build` | 读 `report.json` → TTS → 字幕 → 分镜渲染 → `xfade` 拼接 → 写 `manifest.json` | `--lang both\|zh\|en`、`--run-id <run_id>`、`--dry-run` |
| `verify` | 10 项校验（`V8`~`V12` + `SC-002`/`SC-007`/`SC-008`/`SC-009`/`SC-012`），回写 `manifest.json` | `--run-id <run_id>`、`--strict` |
| `publish` | 把成片复制到前端演示位，发布前自动备份 | `--apply`（默认 dry-run）、`--target <目录>`、`--run-id <run_id>` |

全局参数：`--content-dir`、`--runs-dir`、`--run-id`、`--min-data-points`、`--frontend-url`、`--backend-url`、
`--headless`/`--headed`、`--json`、`--verbose`、`--timeout`。

> **本节不接受任何凭据参数**（无 `--api-key` / `--token` 之类）：模型凭据只存在服务端。

`--run-id` 语义：`probe` 总是新建目录；`build`/`verify`/`publish` 省略时取**最新**的 run 目录
（`20261005-184829-cdc733d` 这种固定宽度命名，字典序即时间序）。要复现或核对既有产物，请显式指定。

## 4. 产物结构

```text
chat-data-assistant\video\runs\<YYYYMMDD-HHMMSS>-<short-sha>\
├── demo-zh.mp4        中文版成片（可直接双击播放）
├── demo-en.mp4        英文版成片
├── report.json        probe 报告：每个候选的判定、数据点数、美观结论与推荐排序
├── manifest.json      产物清单：sha256、逐分镜溯源、10 项校验结果、published
├── plates\            元素级图表底图（页面底图 page-lang-zh/en.png 也在此）
├── clips\             交互片段（--no-clips 时为空）
├── audio\             旁白 MP3 与逐词时间轴
├── subs\              中英 .ass / .srt 字幕
└── segments\          逐分镜片段（拼接前的中间产物）
```

`run_id` 里的 `short-sha` 取内容定义（`content/*.toml`）sha256 的前 7 位：**内容一改，run_id 就变**，
所以历史成片天然不会被覆盖（FR-022 / SC-010）。`video/runs/` 已在 `.gitignore` 中。


## 5. 内容怎么改（不需要动代码）

| 想改什么 | 改哪里 | 说明 |
|----------|--------|------|
| 换一条提问 / 加一条候选 | `content/candidates.toml` 的 `[[candidate]]` | 句首要有绘图动词（绘制/画/…散点图/柱状图），句式用「分组 / 趋势 / 对比 / 分布」 |
| 换手动绘图素材 | `content/candidates.toml` 的 `[[manual]]` | 指定 `chart_type` 与字段名（字段名取自 `/api/bootstrap` 的真实列名） |
| 改旁白 / 字幕 / 顺序 | `content/scenes.toml` 的 `[[shot]]` | 中英必须同时给；`order` 保持 1..N 连续 |
| 调阈值（如数据点下限） | `settings.py` | `min_data_points` 默认 10（FR-008） |
| 改分辨率 / 帧率 / 编码 | `settings.py` | 默认 `1920x1080`、30fps、`libx264 -preset medium -crf 20`、`+faststart` |
| 换配音音色 | `settings.py` | 默认 `zh-CN-XiaoxiaoNeural` / `en-US-AriaNeural` |
| 换字幕字体 | `settings.py` | 默认 `C:\Windows\Fonts\msyh.ttc`（缺失则中文显示为方块） |

改完内容定义后，重新执行 `probe → build → verify` 即可；字段级校验规则见
[`contracts/content-definition.md`](../../../specs/001-intro-video-generator/contracts/content-definition.md)，
数据模型见 [`data-model.md`](../../../specs/001-intro-video-generator/data-model.md)。

## 6. 退出码

| 码 | 含义 | 触发示例 |
|----|------|----------|
| `0` | 成功 | 全部 `blocking` 校验通过 |
| `2` | 用法错误 | 未知子命令、缺必填参数、`--min-data-points` 非正整数 |
| `3` | 前置条件不满足 | 后端不可达、凭据失效、FFmpeg 缺 `libx264`（`doctor`/`probe`/`build` 均可能） |
| `4` | 界面锚点漂移 | `ui_surface` 硬锚点缺失（见 `contracts/ui-surface.md`） |
| `5` | 内容定义非法 | TOML 语法错误、`order` 不连续、中英缺一、分镜/候选数量越界、`source` 不存在 |
| `6` | 渲染/编码失败 | FFmpeg 非 0 退出、`zoompan`/`xfade` 滤镜不可用、磁盘写失败 |
| `7` | 校验不通过 | `verify` 存在 `blocking` 项失败（分辨率、占比、字幕覆盖、敏感信息等） |
| `8` | 发布被拒绝 | `publish --apply` 备份失败或目标不可写 |

约定：**任何非 0 退出码都不得留下会被误当成成片的文件**。失败时 `stderr` 输出一行
`[E<code>] <检查项>: <原因>`，加 `--json` 时同时输出结构化错误对象。

## 7. 故障排查

| 现象 | 原因 | 处理 |
|------|------|------|
| `doctor` 报 `credential` 失败 | 服务端模型凭据缺失/失效/额度耗尽 | 在服务端配置**新的有效**凭据后重试；本工具不接受任何 Key 参数 |
| `doctor` 报 `schema` 失败 | 后端未加载数据表结构 | 在前端「配置」区完成 schema 加载后重试 |
| `probe` 大量 `table_only` | 提问偏聚合（命中 `data` 意图，只回单行结论） | 改成「分组/趋势/对比/分布」句式后重跑 `probe` |
| `probe` 报 `ui_surface_drift` | 前端 class 名与本工具锚点契约不一致 | 按 `contracts/ui-surface.md` 同步锚点表与 `ui_surface.py` |
| 裸 `build` 报 `E5` 且提示推荐场景不足 | 取到的「最新 run」是**预检失败**的那次（只有空 `report.json`） | 显式指定成功那次的目录：`build --run-id <run_id>`（`probe` 输出的第一行就是 run_id） |
| 字幕中文显示为方块 | 字体缺失 | 确认 `C:\Windows\Fonts\msyh.ttc` 存在，或在 `settings.py` 改 `subtitle_font` |
| `verify` 报 `duration_out_of_range` | 分镜过多/旁白过长 | 在 `scenes.toml` 调整 `duration_sec` 或删减分镜 |
| `build` 报路径已存在 | 同一 `run_id` 重复构建 | 属预期保护（FR-022）；换一次运行，或让 `short-sha` 随内容变化 |
| FFmpeg 未找到 | PATH 未包含 | 把 ffmpeg 的 bin 目录加入 PATH，或在 `settings.py` 设 `ffmpeg_bin` |
| 渲染很慢 | `zoompan` 为 CPU 密集 | 单镜时长控制在 18 秒内；预览时把 `preset` 调为 `faster`（成片仍用 `medium`） |

## 8. 边界与约定

- **只读**：本工具不 import `db/`、不直连数据库、不新增 SQL 执行入口；一切出图都经既有
  `POST /api/query` 驱动真实界面产生（Constitution I）。
- **密钥不出服务端**：不接受凭据参数，所有落盘文本经 `safety.sanitize()` 脱敏（Constitution II）。
- **测试零外部依赖**：`python tests/test_video_*.py` 均可独立运行，不需 pytest / 网络 / 数据库（Constitution III）。
- **双语同步**：所有面向用户的文案必须中英同时提供（Constitution IV）。
- **简单优先**：仅新增两个固定版本的工具依赖，不合并进运行期依赖（Constitution V）。

## 9. 相关文档

- 五分钟上手与验收场景：[`quickstart.md`](../../../specs/001-intro-video-generator/quickstart.md)
- 命令契约（参数、退出码、失败语义）：[`contracts/cli.md`](../../../specs/001-intro-video-generator/contracts/cli.md)
- 内容定义契约（字段与校验）：[`contracts/content-definition.md`](../../../specs/001-intro-video-generator/contracts/content-definition.md)
- 界面锚点契约（A1–A16）：[`contracts/ui-surface.md`](../../../specs/001-intro-video-generator/contracts/ui-surface.md)
- 数据模型（`report.json` / `manifest.json`）：[`data-model.md`](../../../specs/001-intro-video-generator/data-model.md)
- 需求与技术方案：[`spec.md`](../../../specs/001-intro-video-generator/spec.md) · [`plan.md`](../../../specs/001-intro-video-generator/plan.md)
- 任务清单与进度：[`tasks.md`](../../../specs/001-intro-video-generator/tasks.md)
