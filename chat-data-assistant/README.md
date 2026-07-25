# chat-data-assistant

项目骨架：数据库智能绘图助手（MVP）。

目录结构已按需求创建。下一步可以逐步实现各模块的具体逻辑：
- Schema 加载与验证
- Text-to-SQL 与 LLM 集成
- SQL 安全校验与执行
- Streamlit 前端交互与图表渲染

运行：创建虚拟环境并安装 `requirements.txt`，然后运行 `streamlit run app.py`。
结合 README 和你们要做的 **Chat with Data**，可以把整个功能划成 **6 个大块**。每一块职责清晰、可以分给不同人做，也方便按顺序开发。

---

## 总体架构一览

```text
┌─────────────────────────────────────────────────────────────┐
│  ① 应用入口与界面层（Streamlit UI）                           │
├─────────────────────────────────────────────────────────────┤
│  ② 会话与状态管理（Session / Chat History）                   │
├─────────────────────────────────────────────────────────────┤
│  ③  schema 管理（ORM / 表结构，只填一次）                     │
├─────────────────────────────────────────────────────────────┤
│  ④ AI 对话与 Text-to-SQL（LLM 核心）                        │
├─────────────────────────────────────────────────────────────┤
│  ⑤ 数据库查询执行（PostgreSQL + 安全）                       │
├─────────────────────────────────────────────────────────────┤
│  ⑥ 数据展示与可视化（表格 + 图表）                            │
└─────────────────────────────────────────────────────────────┘
         ↑                    ↑                    ↑
    侧边栏配置           主界面聊天区            底部/右侧结果区
```

---

## ① 应用入口与界面层（UI Shell）

**做什么：** 整个 Streamlit 应用的框架和布局。

| 子项 | 内容 |
|------|------|
| 入口 | `app.py` / `main.py`，页面路由（若有多页） |
| 侧边栏 | 数据库连接、ORM 输入、连接状态、清空会话 |
| 主区 | 聊天消息列表 + `st.chat_input` |
| 结果区 | SQL 展示、数据预览、图表配置与渲染 |

**产出：** 用户能打开页面、看到分区，暂时可先接假数据。

**建议文件：** `app.py`、`ui/sidebar.py`、`ui/chat_panel.py`、`ui/result_panel.py`

---

## ② 会话与状态管理（Session / Chat）

**做什么：** Chat Data 的“多轮对话”能力，Streamlit 每次交互会重跑脚本，状态必须在这里管。

| 要缓存的内容 | 用途 |
|--------------|------|
| `messages` | 用户/助手聊天记录 |
| `orm_schema` | 表结构（只填一次） |
| `db_engine` | 数据库连接 |
| `last_sql` / `last_df` | 最近一次查询，方便追问和画图 |
| `chart_config` | 用户选的图类型、X/Y 轴 |

**典型流程：**

```text
用户发消息 → 追加到 messages → 调 AI 模块 → 追加助手回复 → rerun 后从 session 恢复界面
```

**产出：** 多轮对话不丢上下文；「在上一条结果上再筛选」可以实现。

**建议文件：** `core/session_state.py`、`core/chat_history.py`

---

## ③ Schema 管理（ORM / 表结构）

**做什么：** 实现 README 里「ORM 只输入一次」。

| 子项 | 内容 |
|------|------|
| 输入 | 文本框粘贴 SQLAlchemy 模型，或上传 JSON/DDL |
| 校验 | 格式是否正确、能否解析出表名和字段 |
| 缓存 | 写入 `st.session_state['orm_schema']` |
| 摘要 | 表太多时生成精简 schema，控制 LLM Token |

**产出：** 后续 Text-to-SQL 始终基于同一份表结构，不用每轮重复输入。

**建议文件：** `schema/loader.py`、`schema/validator.py`、`schema/summarizer.py`

---

## ④ AI 对话与 Text-to-SQL（LLM 核心）

**做什么：** 把自然语言变成可执行的 SQL，并支持多轮修正。这是 Chat Data 的“大脑”。

可再拆成 3 个小层：

| 小层 | 职责 |
|------|------|
| **Prompt 构建** | System Prompt（PostgreSQL 专家、只允许 SELECT）+ 注入 schema + 历史对话 |
| **LLM 调用** | 封装 OpenAI / 通义 / DeepSeek 等 API，统一请求/响应格式 |
| **SQL 解析与安全** | 从回复里提取 SQL；拒绝 DROP/INSERT 等；可选 SQL 语法预检 |

**多轮场景示例：**

```text
用户：查 Mg 相关材料的脱氢数据
助手：生成 SQL → 执行 → 返回表格摘要

用户：只要起始温度大于 500 的
助手：基于上一轮 SQL + 新条件改写 SQL
```

**可选增强：** SQL 执行失败时，把错误信息回传给 LLM 做 Self-Correction（README 4.3 已提到）。

**建议文件：** `ai/llm_client.py`、`ai/prompts.py`、`ai/text_to_sql.py`、`ai/sql_guard.py`

---

## ⑤ 数据库查询执行（DB Executor）

**做什么：** 安全、稳定地跑 LLM 生成的 SQL。

| 子项 | 内容 |
|------|------|
| 连接 | `create_engine`，只读账号 `read_only` |
| 执行 | `pandas.read_sql` → DataFrame |
| 异常 | 捕获语法/权限错误，返回结构化错误给 AI 模块 |
| 限制 | 最大行数、超时，避免一次查爆内存 |

**产出：** 输入 SQL，输出 DataFrame 或明确错误信息。

**建议文件：** `db/connection.py`、`db/executor.py`、`db/exceptions.py`

---

## ⑥ 数据展示与可视化（Display & Charts）

**做什么：** 查完数据后的展示和画图，对应 README 4.4，也对接你之前截图里的「可视化分析」。

| 子项 | 内容 |
|------|------|
| 数据预览 | `st.dataframe`，分页/行数提示 |
| SQL 展示 | `st.code(sql, language="sql")` |
| 图表配置 | 图类型、X/Y 轴、分组字段（selectbox / multiselect） |
| 渲染 | Streamlit 原生图 或 Plotly（散点、边际分布等高级图） |
| 中文 | Plotly 字体配置，避免乱码 |

**两种模式（可分期做）：**

1. **半自动（MVP）：** AI 只负责 SQL，用户手动选图类型和字段  
2. **全自动（进阶）：** LLM 同时建议 chart_type、x_col、y_col，用户可改  

**建议文件：** `viz/data_preview.py`、`viz/chart_config.py`、`viz/renderer.py`

---

## 推荐开发顺序（分阶段交付）

```text
Phase 1 — 能跑通一条链路（1～2 周）
  ③ Schema 管理（简化版）
  ⑤ 数据库连接 + 手动 SQL 查询
  ⑥ 表格预览 + 一种简单图表
  ① 最简 UI（无聊天，一个输入框即可）

Phase 2 — 接上 AI（核心）
  ④ Text-to-SQL + SQL 安全校验
  ② 基础 session_state（ORM、last_df）

Phase 3 — Chat Data 体验
  ① st.chat_input + 消息气泡
  ② 完整聊天历史 + 多轮上下文
  ④ Self-Correction（SQL 错了自动重试）

Phase 4 — 体验与优化
  ⑥ 高级图表（联合分布、高清 DPR 等）
  schema 摘要、查询限流、导出 CSV/图片
```

---

## 目录结构建议（6 块对应 6 个包）

```text
chat-data-assistant/
├── app.py                    # ① 入口
├── ui/                       # ① 界面
│   ├── sidebar.py
│   ├── chat_panel.py
│   └── result_panel.py
├── core/                     # ② 会话状态
│   ├── session_state.py
│   └── chat_history.py
├── schema/                   # ③ Schema
│   ├── loader.py
│   └── summarizer.py
├── ai/                       # ④ LLM + Text-to-SQL
│   ├── llm_client.py
│   ├── prompts.py
│   ├── text_to_sql.py
│   └── sql_guard.py
├── db/                       # ⑤ 数据库
│   ├── connection.py
│   └── executor.py
├── viz/                      # ⑥ 可视化
│   ├── data_preview.py
│   └── renderer.py
├── config.py                 # API Key、DB 默认配置
└── requirements.txt
```

---

## 6 大块之间的数据流（一次完整对话）

```text
用户输入自然语言
    ↓
② 写入 chat history
    ↓
③ 读取 orm_schema
    ↓
④ LLM：history + schema + question → SQL
    ↓
④ sql_guard：只允许 SELECT
    ↓
⑤ executor：SQL → DataFrame
    ↓（失败则回到 ④ Self-Correction）
② 缓存 last_sql、last_df
    ↓
⑥ 展示表格 + 用户/系统选图 → 渲染图表
    ↓
② 助手消息写回 chat history
```

---

## 小结

| 大块 | 一句话 | 是否 Chat Data 特有 |
|------|--------|---------------------|
| ① UI | 页面布局与交互 | 部分（chat 组件） |
| ② Session | 多轮状态与历史 | **是，Chat 核心** |
| ③ Schema | ORM 一次注入 | 文档已有 |
| ④ AI / Text-to-SQL | 自然语言 → SQL | **是，核心** |
| ⑤ DB | 安全查库 | 文档已有 |
| ⑥ Viz | 表格与图表 | 文档已有，可复用现有可视化 |

你们需要 **自己开发这 6 块**；和 pip 的 `models` 无关。若已有「可视化分析」页面，**第 ⑥ 块最值得复用**，**第 ④ + ② 块是 Chat Data 的新增重点**。

你下一个问题如果是「Phase 1 每个文件写什么」或「② 和 ④ 怎么设计多轮 Prompt」，可以继续问，我可以按模块拆到函数级别。