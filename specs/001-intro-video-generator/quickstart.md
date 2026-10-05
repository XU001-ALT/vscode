# Quickstart: 客户演示视频生成器

**Feature**: `001-intro-video-generator` | **Date**: 2026-10-05 | **Plan**: [plan.md](./plan.md) | **Contracts**: [contracts/cli.md](./contracts/cli.md)

本文件面向「第一次使用本工具的人」：从零到拿到可发给客户的中英双语成片，并给出可逐条核验的验收场景（含 SC-011 要求的「无剪辑经验者 5 分钟内完成一次生成」）。

## 0. 前置条件

| 条件 | 检查命令 | 期望 |
|------|----------|------|
| Python ≥ 3.11 | `chat-data-assistant\venv\Scripts\python.exe -V` | `Python 3.14.x` |
| 后端已启动 | `curl http://127.0.0.1:8000/api/bootstrap` | HTTP 200 |
| 前端已启动 | 浏览器打开 `http://localhost:5173/` | 页面正常 |
| schema 就绪 | 同 `/api/bootstrap` 的 `schema.tables` | 非空数组 |
| 服务端模型凭据 | 在前端问一句话能出图 | 有结果、无 `llm_auth` |
| FFmpeg 9 | `ffmpeg -version` | 含 `libx264`、`libass` |
| 浏览器 | `msedge.exe` 或 `chrome.exe` | 存在（走系统通道，无需 `playwright install`） |
| 中文字体 | `C:\Windows\Fonts\msyh.ttc` | 存在（否则字幕中文会显示为方块） |

前后端启动：直接运行 `chat-data-assistant\启动.bat`（或 `start.bat`），等待前端提示 `Local:` 即就绪。

## 1. 安装（一次性）

```powershell
cd d:\vscode\chat-data-assistant
.\venv\Scripts\python.exe -m pip install -r tools\video\requirements-video.txt
```

> 只装两个固定版本的工具依赖（`playwright==1.63.0`、`edge-tts==7.2.8`）；**不修改** `requirements.txt`，不影响产品运行期与 Docker 构建。Playwright 使用系统已安装的 Edge/Chrome 通道，因此**不需要**执行 `playwright install`（可省约 150 MB 下载）。

## 2. 五分钟跑通（对应 SC-011）

```powershell
cd d:\vscode\chat-data-assistant

# ① 体检：确认 9 项前置条件（不产生任何产物）
.\venv\Scripts\python.exe -m tools.video.cli doctor

# ② 探测：实测全部候选提问，输出可用性判定与推荐排序
.\venv\Scripts\python.exe -m tools.video.cli probe

# ③ 合成：按推荐分镜产出中英两个成片（无需人工剪辑）
.\venv\Scripts\python.exe -m tools.video.cli build

# ④ 校验：核对分辨率/帧率/时长/字幕覆盖/图表占比/敏感信息
.\venv\Scripts\python.exe -m tools.video.cli verify

# ⑤ 发布（可选）：把成片写进前端演示位；默认 dry-run，需显式 --apply
.\venv\Scripts\python.exe -m tools.video.cli publish --apply
```

生成的产物固定在：

```text
chat-data-assistant\video\runs\<YYYYMMDD-HHMMSS>-<short-sha>\
├── demo-zh.mp4        中文版成片（可直接双击播放）
├── demo-en.mp4        英文版成片
├── report.json        probe 报告（每个候选的判定、数据点数、美观结论）
├── manifest.json      产物清单（sha256、逐分镜溯源、10 项校验结果）
├── plates\  clips\  audio\  subs\  segments\
```

## 3. 内容怎么改（不需要动代码）

| 想改什么 | 改哪里 | 说明 |
|----------|--------|------|
| 换一条提问 / 加一条候选 | `tools/video/content/candidates.toml` 的 `[[candidate]]` | 用「分组 / 趋势 / 对比 / 分布」句式；避免「多少 / 总计」这类聚合问法（会只出单行结果） |
| 换手动绘图素材 | `candidates.toml` 的 `[[manual]]` | 指定 `chart_type` 与字段名（字段名取自数据表列名） |
| 改旁白 / 字幕 / 顺序 | `tools/video/content/scenes.toml` 的 `[[shot]]` | 中英必须同时给；`order` 保持 1..N 连续 |
| 调阈值（如数据点下限） | `tools/video/settings.py` | `min_data_points` 默认 10（FR-008） |

改完内容定义后**重新执行 `probe → build → verify`** 即可；内容定义的 sha256 变化会让新产物落到新的 `run_id`，历史成片不受影响（FR-022、SC-010）。

## 4. 端到端验证场景

按顺序执行即可逐条覆盖成功判据（括号内为对应判据）：

### 场景 A — 一键产出可直接播放的成片（SC-001、SC-002、SC-009）

1. 执行 §2 的 ①→④，记录起止时间。
2. 期望：全程 **≤ 30 分钟**、**0 次人工干预**（SC-001）。
3. 双击 `demo-zh.mp4`：Windows Media Player / 播放器 / Chrome 均可直接播放，无需装解码器（SC-002）。
4. `verify` 输出 `V8`、`SC-002`、`SC-009` 三项 `ok=true`，实测为 `1920x1080 @ 30 fps`。

### 场景 B — 画面内容合规（SC-006、SC-012、FR-002/003/004）

1. 打开 `report.json`，`candidates[]` 中**所有** `recommended=true` 的条目其 `verdict` 必须是 `chart_ok`（不得有 `table_only`/`failed` 被采用）。
2. 完整看片：出现「输入问题 → 图表渲染」的连续画面，且全程**无报错页、无空白图、无纯表格画面**（SC-006）。
3. 检索 `manifest.json` 的 `sensitive_findings` 必须为 `0`；也可人工在片中确认无密钥、连接串、真实库名/账号、内网地址（SC-012）。

### 场景 C — 图表质量（SC-004、SC-005）

1. `manifest.json` → `verification` 中 `V10`、`V11` 均 `ok=true`（`V10`：问答出图 ≥ 3 且手动绘图 ≥ 1；`V11`：进片图表数据点 ≥ 10 且美观四项全过）。
2. 抽查 `report.json` 中任意 `recommended=true` 条目的 `data_points ≥ 10`、`aesthetics.no_label_overlap/no_text_truncation/axes_legend_complete/theme_consistent` 全为 `true`。
3. 人工看片：片中确实出现 ≥ 3 个问答出图样例与 ≥ 1 个手动绘图样例，且无标签重叠、无文字截断。

### 场景 D — 双语一致性（SC-003、FR-005、FR-021）

1. 确认一次生成产出**两个独立视频文件**（`demo-zh.mp4` 与 `demo-en.mp4`），而非一版加双语字幕（FR-005）。
2. 对比 `manifest.json` 中 `produced_videos[0].scene_count == produced_videos[1].scene_count`，且 `shots[].order` 序列一致（`V9` 校验项）。
3. 看中文版：所有可见文字与旁白为中文，无英文残留；看英文版：全为英文，无中文残留。
4. 片中应包含一处**界面语言切换**画面（FR-012）。

### 场景 E — 图表作为背景组织全片（SC-007、FR-013、FR-015）

1. `verify` 的 `SC-007` 项 `ok=true`（`chart_background_ratio ≥ 0.8`）。
2. 看片确认：所有画面以图表底图为背景并配推镜；同时至少有一个分镜专门解释「图表以外的界面区域」（FR-015，`kind=ui_explain`）。

### 场景 F — 字幕覆盖（SC-008、FR-014）

1. `verify` 的 `SC-008` 项 `ok=true`（`subtitle_coverage == 1.0`）。
2. 打开 `runs/<run_id>/subs/demo-zh.srt`，与 `scenes.toml` 的 `narration` 文本逐条比对：文本一致（字幕由旁白文本直接生成，不经语音识别）。
3. 看片确认：凡有旁白处必有字幕，且中文字幕无方框乱码（字体来自 `msyh.ttc`）。

### 场景 G — 重复执行不覆盖历史（SC-010、FR-022）

```powershell
# 记录当前历史产物的校验值
Get-FileHash chat-data-assistant\video\runs\<旧run_id>\demo-zh.mp4 -Algorithm SHA256

# 再跑一次
.\venv\Scripts\python.exe -m tools.video.cli probe
.\venv\Scripts\python.exe -m tools.video.cli build

# 复核：旧文件的 SHA256 必须与之前完全一致；新产物在全新 run_id 下
Get-FileHash chat-data-assistant\video\runs\<旧run_id>\demo-zh.mp4 -Algorithm SHA256
```

期望：第二次产出新的 `run_id` 目录且构建成功，旧目录内容不变，`V12` 校验项 `ok=true`。

### 场景 H — 快速失败不留半成品（FR-023、US1-AS3）

1. 停掉后端（或把模型凭据改成无效值），执行 `probe`。
2. 期望：以非 0 退出码结束，输出明确点名缺失项（如 `credential`）；`runs/<run_id>/` 内**不存在** `demo-*.mp4`、`segments/`、`manifest.json`。
3. 恢复后端后可重跑成功。

## 5. 故障排查

| 现象 | 原因 | 处理 |
|------|------|------|
| `doctor` 报 `credential` 失败 | 服务端模型凭据缺失/失效/额度耗尽 | 在服务端配置一份**新的、有效的**模型凭据后重试；本工具不接受任何 Key 参数 |
| `doctor` 报 `schema` 失败 | 后端未加载数据表结构 | 在前端「配置」区完成 schema 加载后重试 |
| `probe` 大量 `table_only` | 提问写法偏聚合（命中 `data` 意图） | 把提问改成「分组/趋势/对比/分布」句式后重跑 `probe`（见 research R3） |
| `probe` 报 `ui_surface_drift` | 前端 class 名与本工具锚点契约不一致 | 按 [contracts/ui-surface.md](./contracts/ui-surface.md) 同步锚点表与 `ui_surface.py` 后重跑 |
| 字幕中文显示为方块 | 字体缺失 | 确认 `C:\Windows\Fonts\msyh.ttc` 存在；或在 `settings.py` 改 `subtitle_font` |
| `verify` 报 `duration_out_of_range` | 分镜过多/旁白过长 | 在 `scenes.toml` 调整 `duration_sec` 或删减分镜 |
| `build` 报路径已存在 | 同一 `run_id` 重复构建 | 属预期保护（FR-022）；换一次运行或改用新的 `run_id`（内容定义有变更时 `short-sha` 会自动变化） |
| 裸 `build` 报 `E5`（推荐场景不足） | 不带 `--run-id` 时取「最新 run」，而最新那次可能是**预检失败**留下的空报告 | 显式指定成功那次：`build --run-id <run_id>`（`probe` 首行输出即为 run_id） |
| FFmpeg 未找到 | PATH 未包含 | 把 `D:\ffmpeg\ffmpeg-9.0.1-full_build\bin` 加入 PATH，或在 `settings.py` 设 `ffmpeg_bin` |
| 渲染很慢 | `zoompan` 为 CPU 密集 | 单镜时长控制在 18 秒内；或临时把 `preset` 调为 `faster` 做预览（成片仍用 `medium`） |

## 6. 清理与回滚

```powershell
# 删除某次运行的全部产物（只影响该 run_id，不触碰历史）
Remove-Item -Recurse -Force chat-data-assistant\video\runs\<run_id>

# 回滚已发布的演示位（publish 会在发布前自动备份）
Copy-Item chat-data-assistant\frontend\public\demo.<时间戳>.bak.mp4 `
          chat-data-assistant\frontend\public\demo.mp4 -Force
```

`runs/` 目录已在 `.gitignore` 中，不会污染仓库；只有内容定义（`content/*.toml`）与代码进 git。