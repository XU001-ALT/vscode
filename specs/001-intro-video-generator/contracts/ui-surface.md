# Contract: UI Surface（界面锚点契约）

**Feature**: `001-intro-video-generator` | **Version**: 1.0.0 | **Date**: 2026-10-05

本契约声明视频生成工具**依赖的前端界面锚点**（DOM 选择器）。这些锚点全部取自前端**既有**实现（未新增任何 `data-testid`，也未修改前端代码），因此必须显式记录，避免前端改版后工具静默失效。

## 1. 依赖方式与边界

- 本工具**只读**界面：不点击业务按钮以外的控件，不写入任何表单字段（除提问输入框），不修改前端源码。
- 前端**不得**随意改动本契约列出的选择器；若确需改动，见 §4 变更协议。
- 所有选择器都基于**语义 class 名**与**稳定的库生成节点**（Plotly 的 `.js-plotly-plot`），不依赖文案文本（文案随中英切换变化）。

## 2. 锚点清单

| # | 锚点（选择器） | 来源文件 | 用途 | 缺失后果 |
|---|----------------|----------|------|----------|
| A1 | `.app`（含 `data-lang="zh"｜"en"`） | `src/App.tsx:34`、`src/index.css:16,34` | 判定当前主题（`zh`=深蓝暗色，`en`=浅色），用于美观判定的配色一致性 | 无法判定主题 → `theme_consistent` 判失败 |
| A2 | `header .lang-btn` | `src/components/Header.tsx:13` | 触发中英切换，用于 `bilingual_demo` 分镜 | 无法拍摄语言切换画面（FR-012） |
| A3 | `.query-box textarea` | `src/components/QueryPanel.tsx:55` | 输入候选提问（`fill`/逐字输入） | probe 无法执行 → 全部候选 `failed` |
| A4 | `.query-box button` | `src/components/QueryPanel.tsx:68` | 提交提问 | 同上 |
| A5 | `.loading-block`（含 `.spinner`） | `src/components/QueryPanel.tsx:96-97` | 判定「查询进行中」，用于录制真实的加载态画面 | 录屏切点不准（非阻断） |
| A6 | `.result-area`（可能附加 `.manual-open`） | `src/components/QueryPanel.tsx:73` | 结果区根节点；`manual-open` 表示手动绘图已展开 | 无法区分手动绘图模式（FR-011） |
| A7 | `.result-body` | `src/components/QueryPanel.tsx:94` | 结果区容器，判定「无结果/有结果」 | 判定上下文丢失（阻断） |
| A8 | `.msg.error`、`.msg.error .err-detail` | `src/components/QueryPanel.tsx:113-115` | 判定失败态并抓取错误文本（脱敏后写入报告） | `failed` 判定退化，`error_excerpt` 缺失 |
| A9 | `.ai-answer`、`.ai-answer-body` | `src/components/QueryPanel.tsx:120-121` | 识别闲聊回答（`intent=chat`），避免误判为图表 | 可能误判 `table_only`（不危及正确性） |
| A10 | `.chart-view` | `src/components/ChartView.tsx:503` | 图表区根节点；**截图目标**（元素级 plate） | 无法采集图表底图（阻断） |
| A11 | `.chart-view-body` | `src/components/ChartView.tsx:510` | 图表主体容器（含控件 + 画布） | 截取范围不准 |
| A12 | `.js-plotly-plot`（Plotly 注入） | Plotly 运行时（`plotly.js-dist-min`） | **「真的画出图形」的判定依据** | `chart_ok` 判定退化（阻断） |
| A13 | `.js-plotly-plot .xtick text`、`.ytick text`、`.legend text` | Plotly 生成 | 标签重叠与文字截断量测（FR-009） | 美观判定无法执行（阻断） |
| A14 | `.result-actions` | `src/components/ChartView.tsx:505` | 截图时排除工具栏（重置/导出按钮）不影响判定；用于取景裁剪 | 画面可能含无关按钮（非阻断） |
| A15 | `.mode-toggle` | `src/components/QueryPanel.tsx:77` | 打开/关闭手动绘图 | 无法采集手动绘图样例（FR-011，阻断） |
| A16 | `.manual-sql-box` → `.manual-plot-demo`、`.chart-builder` | `QueryPanel.tsx:87`、`ManualPlotter.tsx:295,271` | 手动绘图区的根节点与图型/字段选择控件 | 手动绘图分镜无法采集（阻断） |

## 3. 健康检查（doctor 的 `ui_surface` 步骤）

`ui_surface.py::check(page)` 在采集前执行，规则：

1. 打开前端首页，等待 `.app` 出现且带 `data-lang`（超时 15 秒）。
2. 断言 A1、A3、A4、A7、A10、A11、A15、A16 存在；任一项缺失 → 抛 `UiSurfaceDrift`，`doctor`/`probe` 以退出码 `4` 失败，并列出缺失项编号。
3. 触发一次最小提问，断言 A12 或 A8 二者之一出现（证明链路真的在动）。
4. 输出一份 `ui_surface` 检查详情（命中的锚点编号 + 未命中的编号），写入 `report.json#preflight[]` 的 `detail`。

> A2、A5、A9、A13、A14 为**软锚点**：缺失时仅告警（写入 `issues`），不阻断。

## 4. 变更协议

1. 前端如需重命名/替换上述任一锚点，必须**同时**更新本文件、`ui_surface.py` 的锚点常量，并在 PR 描述中标注「影响 video 工具链」。
2. 本工具**不得**通过新增 `data-testid` 来绕开脆弱选择器——保持零前端侵入（Constitution IV：契约同步演进）。
3. 前端若要新增页面结构（例如把结果区拆成两个容器），须保持 A7/A10/A12 的语义链（结果区 → 图表区 → Plotly 根节点）可被单一选择器命中，否则视为破坏性变更。
4. 验证方式：`python -m tools.video.cli doctor` 的 `ui_surface` 项必须通过；本文件与 `ui_surface.py` 的锚点集合一致性由 `tests/test_video_content.py` 静态校验（不启动浏览器）。