# Chat Data for Digital Hydrogen（chat-data-assistant）Constitution

## Core Principles

### I. 只读数据边界（NON-NEGOTIABLE）

任何 SQL —— 无论由 LLM 生成、人工输入还是新增代码路径产生 —— 在执行前 MUST 经
`ai/sql_guard.py` 的只读白名单校验，仅放行 `SELECT` / `WITH` / `EXPLAIN` / `SHOW` / `DESCRIBE`。

- 去除字符串字面量与注释后出现多语句的，MUST 一律拒绝。
- 问数（`data`）意图 MUST 只返回单行聚合结果；无聚合函数或多行结果 MUST 被拒绝并给出
  说明，禁止以任何形式批量导出明细。
- 新增执行入口 MUST 复用既有校验，禁止绕过、降级或复制一份宽松实现。

Rationale：本平台承载科研实验数据资产，越权写入与批量导出不可接受，安全边界优先于功能便利。

### II. 密钥永不出服务端（NON-NEGOTIABLE）

用户 LLM API Key MUST 只保存在服务端（会话级存储），前端只允许接收掩码值。

- 任何来源的 Key MUST NOT 以明文出现在源码、临时脚本、配置、日志、错误响应或 git
  历史中；强制使用环境变量或服务端存储。
- 对外错误信息、日志与响应体 MUST 经 `core/secrets.py` 脱敏（过滤 API Key 与 Bearer token）。
- `.env`、`data/` 及任何含密钥的产物 MUST 保持在 `.gitignore` 覆盖范围内。

Rationale：密钥泄漏是最高等级事故，且前端是不可信边界。

### III. 测试零外部依赖可运行

`tests/` 下每个测试文件 MUST 能直接以 `python tests/test_xxx.py` 独立运行，
无需 pytest、数据库、网络或 API Key。

- 外部依赖（LLM、数据库、文件系统副作用）MUST 以 monkeypatch 或替身隔离。
- 新增模块 MUST 附带同目录测试；全量测试 MUST 在任何实现步骤收尾前通过。

Rationale：本仓库既有约定（见 `tests/` 各文件 docstring），保证无环境也能回归。

### IV. 契约与双语文案同步演进

- 后端 MUST 只暴露 `/api/*`；`api/serializers.py` MUST 是 DataFrame → JSON 的唯一出口。
- 接口字段变更 MUST 同步更新前端 `src/api.ts` 与 `src/types.ts`，不得单侧先行。
- 一切面向用户的文案（界面文案、图表标签、AI 说明文字）MUST 同时提供中文与 English。

Rationale：前后端分离部署，契约漂移与单语缺失会直接导致线上白屏或体验断裂。

### V. 简单优先，复用既有技术栈

- MUST 优先使用仓库已声明的依赖（`requirements.txt`、`frontend/package.json`）。
- 新增依赖 MUST 说明理由并固定版本；禁止隐式依赖传递包。
- MUST NOT 引入与现有实现重复的抽象，或超出当前需求的缓存、队列、服务化复杂度。

Rationale：YAGNI。复杂度须以可验证的需求换取。

## 技术栈与运行约束

- **运行时**：Python ≥ 3.11（本机 3.14；`api/compat.py` 兼容 typing 变更）。
- **后端**：FastAPI + Uvicorn，仅提供 `/api/*`；CORS 由 `CORS_ORIGINS` 限制。
- **前端**：React 19 + Vite + TypeScript + Plotly（`plotly.js-dist-min`），构建产物独立部署。
- **数据源**：PostgreSQL（建议只读账号）；schema 由 `schema/` 自动发现并推断外键。
- **会话**：SQLite `data/sessions.sqlite3`（WAL，多 worker 共享），不进 git。

## 开发工作流与质量门禁

- 所有功能开发 MUST 遵循 Spec Kit SDD 流程：constitution → specify → (clarify) → plan →
  (checklist) → tasks → (analyze) → implement → converge。
- MUST NOT 跳过 spec / plan / tasks 直接编写业务代码。
- 每个 `/speckit-*` 执行前 MUST 先读取 `.clinerules/workflows/speckit-<name>.md` 并按其全文执行。
- 每一步完成后 MUST 向用户汇报并等待确认，再进入下一步。
- **质量门禁**（`implement` 收尾前必须全部为绿）：
  1. `python tests/test_*.py` 全量通过；
  2. 前端有改动时 `npm run lint`（oxlint）与 `npm run build`（tsc -b + vite build）通过；
  3. 仅当改动涉及数据链路（SQL 生成 / 执行 / 序列化 / 会话）时，`/api/query` 端到端验证
     通过；纯前端、纯文档、纯脚本类改动不适用本条。

## Governance

- 本 Constitution MUST 优先于其他开发实践；与本文冲突的实现 MUST 修改，或通过显式修订放宽。
- **修订流程**：提出变更 → 说明影响面与迁移方案 → 更新版本号与 `Last Amended` →
  用户批准后生效。
- **版本策略**（语义化）：MAJOR = 删除或重定义原则；MINOR = 新增原则或章节；
  PATCH = 措辞澄清与非语义修订。
- **合规审查**：每次实现收尾前逐条核对本文件；`converge` 阶段复核；提交与评审 MUST 验证合规。

**Version**: 1.0.0 | **Ratified**: 2026-10-05 | **Last Amended**: 2026-10-05
