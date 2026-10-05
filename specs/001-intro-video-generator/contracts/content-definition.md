# Contract: Content Definition（内容定义契约）

**Feature**: `001-intro-video-generator` | **Version**: 1.0.0 | **Date**: 2026-10-05

本契约定义两个**人工可编辑**的内容文件。它们是非开发人员调整成片的唯一入口（FR-016、FR-017），工具只读不写。

| 文件 | 作用 | 谁编辑 |
|------|------|--------|
| `tools/video/content/scenes.toml` | 分镜序列（顺序、类型、素材来源、双语标题/旁白/字幕、时长与镜头运动） | 内容/市场人员 |
| `tools/video/content/candidates.toml` | 候选提问与手动绘图素材（进片候选池） | 内容人员 + 了解数据表列名的人 |

## 1. `scenes.toml` 完整示例

```toml
[meta]
version = "1.0.0"                 # 内容变更时递增；影响 run_id 的 short-sha
target_duration_sec = [120, 180]  # 目标时长区间（秒）
languages = ["zh", "en"]          # 固定

# ── 开场：以图表底图为背景，叠加标题 ─────────────────────────────
[[shot]]
id = "intro"
order = 1
kind = "chart_showcase"           # 复用推荐图表作为背景
source = "trend_monthly"          # 必须指向 candidates.toml 中已判定 chart_ok 的 id
zoom = "in"
background = "blur_plate"
  [shot.title]
  zh = "用一句话问出你的数据"
  en = "Ask your data in one sentence"
  [shot.narration]
  zh = "这是一个面向实验数据的自然语言问答平台。下面用真实提问演示它的能力。"
  en = "This is a natural-language analytics platform for experimental data. Let's see it with real questions."

# ── 问答出图样例（至少 3 个）─────────────────────────────────────
[[shot]]
id = "show_trend_monthly"
order = 2
kind = "chart_showcase"
source = "trend_monthly"
zoom = "in"
  [shot.title]
  zh = "按月份看趋势"
  en = "Trends by month"
  [shot.narration]
  zh = "我们直接问：按月统计各产线的氢气纯度均值变化趋势。系统自动生成查询并绘制折线图。"
  en = "We simply ask: show the monthly trend of average hydrogen purity by production line. The system writes the query and draws a line chart."

[[shot]]
id = "show_compare_units"
order = 3
kind = "chart_showcase"
source = "compare_units"
zoom = "pan_right"
  [shot.title]
  zh = "对比不同装置"
  en = "Compare across units"
  [shot.narration]
  zh = "换一个问题：对比各装置的压力分布。柱状图让差异一目了然。"
  en = "Now a different question: compare pressure distribution across units. The bar chart makes the differences obvious."

# ── 手动绘图样例（至少 1 个）─────────────────────────────────────
[[shot]]
id = "show_manual_bubble"
order = 4
kind = "manual_plot"
source = "manual_bubble"
zoom = "in"
  [shot.title]
  zh = "也可以用手动绘图"
  en = "Or build charts manually"
  [shot.narration]
  zh = "如果更想自己掌控，可以在手动绘图里选择图型与字段，气泡图同样由真实数据生成。"
  en = "If you prefer full control, the manual plotter lets you pick a chart type and fields — this bubble chart uses real data too."

# ── 界面说明（FR-015：解释图表以外的界面区域）────────────────────
[[shot]]
id = "explain_ui"
order = 5
kind = "ui_explain"
zoom = "pan_left"
  [shot.title]
  zh = "界面的其他部分"
  en = "The rest of the workspace"
  [shot.narration]
  zh = "左侧的配置区用于加载数据表结构，结果区可以重置视图或导出 PNG，全程无需写 SQL。"
  en = "The configuration panel loads your schema; the result area can reset the view or export a PNG — no SQL required."

# ── 双语能力展示（恰好 1 个）────────────────────────────────────
[[shot]]
id = "bilingual_toggle"
order = 6
kind = "bilingual_demo"
zoom = "in"
  [shot.title]
  zh = "一键切换中英文"
  en = "Switch language in one click"
  [shot.narration]
  zh = "点击右上角即可切换语言，界面与图表文案随之更新，方便给不同地区的同事演示。"
  en = "One click in the header switches the language across the UI and the charts — handy for different regions."

# ── 收尾 ────────────────────────────────────────────────────────
[[shot]]
id = "outro"
order = 7
kind = "outro"
background = "blur_plate"
  [shot.title]
  zh = "让数据回答你的问题"
  en = "Let your data answer"
  [shot.narration]
  zh = "无需编写查询，也不必等待出图。一句自然语言，就是一张可以汇报的图。"
  en = "No query writing, no waiting for charts. One sentence in plain language, one chart ready to present."
```

> 示例为了短小只列了 7 个分镜；实际内容定义应包含 **8–14 个**分镜，且 `chart_showcase` ≥ 3、`manual_plot` ≥ 1、`ui_explain` ≥ 1、`bilingual_demo` = 1（见 data-model.md §2.2 与 FR-010~FR-015）。

## 2. `scenes.toml` 字段规则

| 键 | 必填 | 规则 | 违反时的错误 |
|----|------|------|--------------|
| `meta.version` | 是 | 语义化版本 | `content_invalid` |
| `meta.target_duration_sec` | 是 | `[min, max]`，`10 <= min < max <= 900` | `content_invalid` |
| `meta.languages` | 是 | 必须为 `["zh", "en"]` | `content_invalid` |
| `shot[].id` | 是 | `^[a-z][a-z0-9_]{2,31}$`，唯一 | `content_invalid` |
| `shot[].order` | 是 | 1..N 连续无重复（工具不自动排序） | `order_not_contiguous` |
| `shot[].kind` | 是 | `chart_showcase`/`manual_plot`/`ui_explain`/`bilingual_demo`/`outro` | `content_invalid` |
| `shot[].source` | 条件 | `chart_showcase`→`candidate.id`；`manual_plot`→`manual.id`；其余必须省略 | `source_not_found` |
| `shot[].title` / `narration` | 是 | 双语都必须非空；`narration` 长度 zh 20–220 / en 15–400 字符 | `content_invalid` / `narration_length_warn` |
| `shot[].subtitle` | 否 | 省略时由 `narration` 自动切分 | — |
| `shot[].duration_sec` | 否 | 3–30 秒；省略时取旁白实测时长（±20% 接受） | `duration_out_of_range` |
| `shot[].zoom` | 否 | `in`/`out`/`pan_left`/`pan_right`（默认 `in`） | `content_invalid` |
| `shot[].background` | 否 | `plate`/`blur_plate`（默认 `plate`） | `content_invalid` |

## 3. `candidates.toml` 完整示例

```toml
[meta]
version = "1.0.0"

# ── 候选提问：一律使用「分组 / 趋势 / 对比 / 分布」句式 ─────────────
[[candidate]]
id = "trend_monthly"
expect_chart = true
  [candidate.prompt]
  zh = "按月统计各产线的氢气纯度均值变化趋势"
  en = "Show the monthly trend of average hydrogen purity by production line"

[[candidate]]
id = "compare_units"
expect_chart = true
  [candidate.prompt]
  zh = "对比各装置的压力分布情况"
  en = "Compare the pressure distribution across all units"

# 关闭 AI 推荐 + 手动选型：先取消勾选「使用 AI 推荐的图表配置」，再指定图型与字段
[[candidate]]
id = "trend_monthly_manual"
expect_chart = true
ai_recommend = false
chart_type = "bar"
fields = ["month", "avg_purity"]
  [candidate.prompt]
  zh = "绘制按月统计的氢气纯度柱状图"
  en = "Plot a bar chart of monthly average hydrogen purity"

[[candidate]]
id = "dist_by_shift"
expect_chart = true
  [candidate.prompt]
  zh = "各班组温度数据的分布对比"
  en = "Compare the distribution of temperature data across shifts"

# 对照项：聚合问法，预期只出单行结论（应被判为 table_only，不进成片）
[[candidate]]
id = "count_total"
expect_chart = false
  [candidate.prompt]
  zh = "一共有多少条实验记录"
  en = "How many experiment records are there in total"

# ── 手动绘图素材：字段名必须是数据表中的真实列名 ────────────────────
[[manual]]
id = "manual_bubble"
chart_type = "bubble"
x_field = "pressure"
y_fields = ["temperature"]
size_field = "duration_min"
color_field = "purity"
  [manual.title]
  zh = "压力—温度—时长的气泡分布"
  en = "Pressure vs temperature bubble map"
```

## 4. `candidates.toml` 字段规则

| 键 | 必填 | 规则 | 违反时的错误 |
|----|------|------|--------------|
| `meta.version` | 是 | 语义化版本 | `content_invalid` |
| `candidate` 数量 | 是 | 8–20 条 | `content_invalid` |
| `candidate[].id` | 是 | 同 `shot.id` 规则，且与 `manual[].id` 全局唯一 | `content_invalid` |
| `candidate[].prompt` | 是 | 双语非空；**不得**仅为「多少/总计/统计/有几个」等聚合问法 | `prompt_not_visual_warn`（告警，仍会实测） |
| `candidate[].expect_chart` | 否 | 默认 `true`；`false` 用于对照项 | — |
| `candidate[].notes` | 否 | 任意文本，写入报告 | — |
| `candidate[].ai_recommend` | 否 | 默认 `true`；`false` 表示采集时取消勾选界面里的「使用 AI 推荐的图表配置」，改用手动选型 | — |
| `candidate[].chart_type` | 否 | 手动指定的图型（`ChartView.CHART_ORDER` 的 12 种之一）；必须与 `ai_recommend = false` 同时给出 | `content_invalid` |
| `candidate[].fields` | 否 | 字符串数组；在该图型的下拉框行里按顺序匹配字段（忽略大小写全等 → 忽略大小写包含，如 `count` 命中 `paper_count`）；必须与 `ai_recommend = false` 同时给出。双轴型图型若横纵轴落到同一列，采集会自动把纵轴换成下一个可用列 | `content_invalid` |
| `manual` 数量 | 是 | ≥ 1 | `insufficient_manual_sources` |
| `manual[].chart_type` | 是 | 取自 `ChartView.CHART_ORDER` 的 12 种之一 | `content_invalid` |
| `manual[].x_field`/`y_fields`/`z_field`/`size_field`/`color_field` | 条件 | 按图型必填（见 data-model.md §2.3）；字段名必须在后端 schema 的列名集合中 | `field_not_found` |
| `manual[].title` | 是 | 双语非空 | `content_invalid` |

## 5. 编辑工作流（非开发人员）

1. 用任意文本编辑器改 `content/*.toml`（UTF-8 无 BOM 保存；建议编辑器装 TOML 语法高亮）。
2. 执行 `python -m tools.video.cli probe`：
   - 内容非法 → 立即退 `5` 并指出「文件 → 分镜/候选 id → 字段」；
   - 合法 → 逐条实测并写出 `report.json`。
3. 打开 `report.json`（或看 `probe` 的表格输出）：
   - `verdict` 为 `table_only` 的候选 → 把提问改写为分组/趋势/对比/分布句式后重试；
   - `data_points < 10` → 换一个更能体现趋势的维度；
   - `aesthetics.issues` 非空 → 换图型或换字段（例如换 `bar` 为 `box`）。
4. 需要进片的分镜数量满足后执行 `build` → `verify`。
5. 若某分镜的 `source` 未通过判定，`build` 会拒绝并列出可用 id，按提示替换 `scenes.toml` 的 `source`。

## 6. 变更影响与版本约定

| 变更 | 影响 |
|------|------|
| 改 `meta.version` | 内容指纹变化 → 新 `run_id`；历史成片不受影响（FR-022、SC-010） |
| 只改文案（`narration`/`title`） | 需要重跑 `build` 才会反映到成片；`probe` 结果仍可复用 |
| 改 `candidate.prompt` | 必须重跑 `probe`（判定结果与素材都会变） |
| 改 `shot.order` 或增删分镜 | 需重跑 `build`；`verify` 会重新核对中英一致性与时长区间 |
| 改 `manual[].chart_type`/字段 | 必须重跑 `probe`（要重新驱动界面绘制并截图） |
| 删除某个被 `shot.source` 引用的 id | `build` 以 `source_not_found` 失败（退 `5`） |

> 两个文件都进 git；`runs/` 目录不进 git。工具的日志与报告都会注明所用内容的 `version` 与 sha256，便于回溯「这个成片是用哪版内容生成的」。