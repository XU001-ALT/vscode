# Chat Data for Digital Hydrogen

面向氢能材料研究的 **智能数据查询与可视化平台**。用一句自然语言提问，平台自动生成并执行只读 SQL，返回统计结果、数据表或图表；无需编写 SQL，也无需安装客户端。

> 前后端完全分离：后端仅提供 `/api/*` 接口（FastAPI），前端为独立静态站点（React + Vite）。Streamlit 旧版界面已废弃。

---

## 功能特性

| 能力 | 说明 |
|------|------|
| **自然语言查询（Text-to-SQL）** | 问题 + 数据库 schema + 多轮对话上下文 → 生成可执行 SQL |
| **智能意图路由** | LLM 首行标注 `INTENT: chart / data / chat`，分别走绘图、单行统计、闲聊/拒答三条路径 |
| **数据安全红线** | 问数模式只允许单行聚合结果；无聚合函数或多行结果一律拒绝，防止批量导出明细 |
| **SQL 自动纠错** | 执行失败时把数据库错误回传 LLM 修正并重试（最多 2 次），记录修复过程 |
| **Schema 自动发现** | 启动即连接数据库，自动读取全部业务表结构，按 token 预算裁剪，并从列名推断表关联（`xxx_id → xxx.id`），标注 `← FK` |
| **图表推荐与手动绘图** | 12 种图表（折线/面积/柱状/散点/气泡/三维散点/热力图/平行坐标/箱线/雷达/饼图/直方图），AI 推荐或手动选表绑轴 |
| **中英双语** | 界面、图表、AI 说明文字均支持中文 / English，右上角一键切换，介绍视频也分中英文 |
| **只读与脱敏** | 仅允许 `SELECT/WITH/EXPLAIN/SHOW/DESCRIBE`；错误信息自动过滤 API Key；用户 Key 只存服务端 |

---

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 19、Vite、TypeScript、Plotly、oxlint |
| 后端 | FastAPI、Uvicorn、Pydantic |
| AI | OpenAI 兼容 API（OpenAI / DeepSeek / 通义 / 中转商等） |
| 数据 | PostgreSQL、SQLAlchemy、psycopg2、pandas |
| 会话 | SQLite（`data/sessions.sqlite3`，多 worker 共享） |
| 部署 | Nginx / Docker / Vite preview |

---

## 架构

```
浏览器 ──→ 前端（React 静态站点，Nginx / CDN）
              │  /api/*
              ▼
        FastAPI:8000（仅提供 /api/*）
              │
     ┌────────┼──────────┬───────────────┐
     ▼        ▼          ▼               ▼
  ai/ 意图路由  schema 自动发现   db/ 只读执行   SQLite 会话
  Text-to-SQL  + 关系推断         (PostgreSQL)
  + 自动纠错
```

### 一次提问的数据流

```
POST /api/query
  → 读取会话历史 + 全局 schema
  → ai/text_to_sql：LLM 输出首行 INTENT
        chat  → 直接返回文字，不生成/执行 SQL
        chart/data → ai/sql_guard 只读校验 → db/executor 执行
              失败 → Self-Correction 循环（最多 2 次）
  → data 意图兜底：无聚合或多行结果 → 拒绝，不返回明细
  → chart 意图成功 → ai/chart_recommendation 推荐图表
  → api/serializers 转 JSON / core/secrets 脱敏错误
  → 写回会话历史（供多轮上下文）
```

---

## 目录结构

```
chat-data-assistant/
├── api/                    # FastAPI 应用
│   ├── main.py             #   入口 + CORS + lifespan（启动后台连库线程）
│   ├── pipeline.py         #   查询管道：意图路由 + 问数兜底
│   ├── sessions.py         #   会话存储（SQLite）
│   ├── serializers.py      #   DataFrame → JSON 安全序列化
│   ├── errors.py           #   错误 → 稳定错误码
│   └── routes/             #   query / config_api / schema_api / system
├── ai/                     # LLM 与 Text-to-SQL
│   ├── llm_client.py       #   OpenAI 兼容调用封装（会话级配置，线程安全）
│   ├── prompts.py          #   System / Few-shot / 纠错 / 图表推荐 prompt
│   ├── text_to_sql.py      #   生成 + 意图解析 + Self-Correction
│   ├── sql_guard.py        #   只读白名单 + 多语句防护
│   └── chart_recommendation.py  # 图表推荐 + 启发式兜底
├── core/
│   ├── bootstrap.py        #   启动自动连库、拉取 schema、失败重试
│   └── secrets.py          #   密钥存储、掩码、错误脱敏
├── db/
│   ├── connection.py       #   连接池（pool_pre_ping）
│   └── executor.py         #   只读执行、行数/超时限制、schema 拉取
├── schema/
│   ├── loader.py           #   文本 / JSON / SQLAlchemy ORM 解析 + 关系推断
│   ├── summarizer.py       #   token 预算裁剪、描述注入、FK 标注
│   ├── descriptions.py     #   本地数据字典加载
│   └── table_descriptions.json
├── frontend/               # React 前端（独立部署）
│   ├── src/components/     #   IntroPanel / QueryPanel / ChartView / ConfigPanel ...
│   ├── public/             #   demo.mp4（中文）/ demo-en.mp4（英文）介绍视频
│   └── vite.config.ts      #   开发态 /api 代理到 127.0.0.1:8000
├── tests/                  # 纯单元测试（无需 pytest，可直接运行）
├── config.py               # 配置（Streamlit secrets > 环境变量 > 默认值）
├── requirements.txt
├── start.bat               # Windows 一键启动前后端
└── deploy.md               # 部署文档（Nginx / Docker / preview）
```

---

## 快速开始

### 环境要求

- Python ≥ 3.11（推荐 3.12；`api/compat.py` 已兼容 3.14 的 typing 变更）
- Node.js ≥ 20、npm
- 可连接的 PostgreSQL（建议只读账号）
- 可访问的 OpenAI 兼容 LLM 服务

### 1. 配置 `.env`

复制 `.env.example` 为 `.env` 并填写：

| 变量 | 说明 |
|------|------|
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | PostgreSQL 连接信息（建议只读账号） |
| `LLM_API_KEY` | 大模型 API Key（留空则需在页面「配置区」填写） |
| `LLM_PROVIDER` | `openai` / `deepseek` / `anthropic` / `local` 等 |
| `LLM_BASE_URL` | API Base URL，如 `https://api.deepseek.com` |
| `LLM_MODEL` | 模型名，留空按 provider 自动选择 |
| `LLM_TEMPERATURE` / `LLM_MAX_TOKENS` | 生成参数 |
| `DEBUG_SQL` | `true` 时把执行的 SQL 写入 `logs/sql_debug.log`（仅服务端） |
| `CORS_ORIGINS` | 允许的前端来源，逗号分隔；不设则默认放行 localhost 常见端口 |

### 2. 启动后端（端口 8000）

```bash
python -m venv venv
venv\Scripts\pip install -r requirements.txt      # Windows
# venv/bin/pip install -r requirements.txt        # Linux / macOS

venv\Scripts\python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### 3. 启动前端（端口 5173，自动代理 `/api`）

```bash
cd frontend
npm install
npm run dev        # 开发：http://localhost:5173
```

打开 **http://localhost:5173**（注意用 `localhost`，Vite 默认绑定 IPv6 的 `::1`）。

### 一键启动（Windows）

```bat
start.bat
```

同时拉起后端（8000）与前端（5173）；缺少 `.env` 或前端依赖时会提示 / 自动安装。

---

## 接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/health` | 健康检查 |
| `GET` | `/api/bootstrap` | 前端首屏轮询：数据库连接状态 + schema 概要 |
| `POST` | `/api/session` | 新建会话，返回 `session_id` |
| `POST` | `/api/query` | 提问：`{session_id, question, lang}` → SQL / 数据 / 图表推荐 / 文字回答 |
| `PUT` | `/api/config/llm` | 设置会话级 LLM 配置（Key 仅存服务端） |
| `GET` | `/api/config/llm/{session_id}` | 读取会话 LLM 配置（Key 以掩码返回） |
| `DELETE` | `/api/config/llm/{session_id}` | 清除会话 LLM 配置 |
| `GET` | `/api/schema/descriptions` | 表数据字典（表名 → 说明） |

---

## 测试

纯单元测试，**无需 pytest、数据库或 API Key**（LLM/网络均被 monkeypatch 隔离），每个文件可独立运行：

```bash
venv\Scripts\python.exe tests\test_schema_loader.py       # 单个文件
# 批量运行
Get-ChildItem tests\test_*.py | ForEach-Object { venv\Scripts\python.exe $_ }
```

覆盖：schema 解析/摘要/校验、序列化、密钥脱敏、错误分类、意图路由、图表推荐、LLM 客户端、SQL 安全、并发配置隔离。

前端静态检查：

```bash
cd frontend && npm run lint      # oxlint
cd frontend && npm run build     # tsc -b + vite build
```

---

## 部署

完整步骤见 **[deploy.md](deploy.md)**（Nginx 反向代理、Docker、Vite preview 三种方式）。

要点：
- 后端只暴露 `/api/*`，前端构建时用 `VITE_API_BASE_URL` 指向后端地址；
- 后端通过 `CORS_ORIGINS` 限制允许的前端来源；
- `.env` 含密钥，通过环境变量注入，不打入镜像 / 不进 git。

---

## 安全设计

- **只读 SQL**：白名单前缀 + 特殊处理字符串/注释后的多语句检测，拒绝 `DROP/DELETE/UPDATE` 等写操作。
- **批量拉取防护**：问数意图强制单行聚合，服务端正则兜底，拒绝明细导出。
- **密钥隔离**：用户 API Key 只存服务端，前端仅拿到掩码；错误信息统一过滤 Key 与 Bearer token。
- **数据库最小权限**：建议使用只读账号、限制连接数与单次返回行数。
- **会话存储**：`data/sessions.sqlite3` 已加入 `.gitignore`，不随代码发布。

---

## 常见问题

| 现象 | 排查 |
|------|------|
| 页面打开但「数据库连接失败」 | `.env` 是否正确；服务器到 DB 的 5432 端口是否连通 |
| 提问报 LLM 相关错误 | `.env` 的 `LLM_API_KEY` / `LLM_BASE_URL`，或在页面配置区填写 |
| 前端 403 / 跨域错误 | 后端 `CORS_ORIGINS` 是否包含前端域名 |
| 前端 404 / 连接被拒 | `VITE_API_BASE_URL` 是否正确；后端是否在运行 |
| `127.0.0.1:5173` 打不开 | Vite 绑定 IPv6，改用 `http://localhost:5173` |
| 只改了前端代码 | `cd frontend && npm run build` 后刷新，无需重启后端 |

---

## 相关文档

- [deploy.md](deploy.md) — 部署指南
- [UI_V9_CHANGELOG.md](UI_V9_CHANGELOG.md) — 界面改版记录
