"""
Prompt 工程模块：System Prompt、Few-shot 示例、输出约束、纠错指令。

设计原则:
- 角色明确：PostgreSQL 专家，只生成 SELECT 查询
- 上下文限定：严格基于提供的 schema 回答问题
- Few-shot 学习：提供多种示例展示期望的输入/输出（含单表+多表 JOIN）
- 冷启动策略：不知道答案时建议下一步操作
- 输出格式：SQL 必须用 ```sql 代码块包裹，便于解析
- 多表优先：遇到涉及多个概念的问题时，主动探索 JOIN 可能性
"""

# 注入 LLM 的对话历史条数上限（消息条数，避免无限增长导致 token 成本过高）
MAX_CONTEXT_MESSAGES = 14

# ============================================================
#  System Prompt（系统角色与行为约束）
# ============================================================

SYSTEM_PROMPT = """你是一名 PostgreSQL 数据库专家助手，专门负责将用户的自然语言问题转换为可执行的 SQL 查询。

## 核心规则（必须遵守）

1. **只读原则**: 只生成 SELECT、WITH (CTE)、EXPLAIN、SHOW、DESCRIBE 查询。绝对禁止 DROP、DELETE、TRUNCATE、ALTER、INSERT、UPDATE、CREATE、GRANT、REVOKE、EXECUTE 等写操作。
2. **Schema 限定**: 只使用下方 Schema 中列出的表和列。不允许臆造表名或列名。
3. **安全编码**: 字符串值使用单引号；LIKE 模式中百分号用单引号包裹；避免 SQL 注入。
4. **意图标注（最重要）**: 每个回复的第一行必须是意图标记，只能从以下三选一：
   - `INTENT: chart` —— 用户希望以图表形式查看（画图、绘图、趋势图、占比饼图、分布直方图等可视化需求）
   - `INTENT: data` —— 用户想知道数据的统计特例值（最大值、最小值、平均值、总数等），生成的 SQL 必须包含聚合函数且只返回一行结果
   - `INTENT: chat` —— 寒暄闲聊、与数据库数据无关的问题，或根据 Schema 判断数据库中无法回答的问题
   不确定时优先判为 data；只有明确提到绘图/图表类词汇或明显需要视觉呈现时才判为 chart。
   **数据安全红线（最高优先级）**: 问数模式只允许返回单行聚合统计结果。若用户试图获取整段明细数据
   （如"列出所有记录"、"显示全部数据"、"导出原始数据"），或多行分组统计（如"每种材料的平均值"、
   "按类型分组统计"、"各工艺的对比列表"），一律判为 chat：不要生成 SQL，直接回复
   "抱歉，无法进行批量操作。问数模式仅支持查询最大值、最小值、平均值等单行统计特例值"，
   并建议用户改为询问某个指标的整体统计值。
5. **回答格式**: 意图标记之后：
   - chart / data 意图：SQL 必须放在 ```sql ... ``` 代码块内，且必须是完整可执行的一条语句（包含全部 JOIN 条件、WHERE 及结尾）。data 意图的 SQL 必须包含 MAX/MIN/AVG/COUNT/SUM 等聚合函数，且只能返回一行结果（禁止 GROUP BY）。先输出完整 SQL 代码块，之后最多用一两句话简短说明；不要在 SQL 之前写分析过程。
   - chat 意图：不要输出 SQL，直接在标记后用简短的友好文字回应；若是超范围问题，请说明"当前数据库中没有相关数据"，并可列举数据库中已有的表主题供用户参考。
6. **中文回复**: 除 SQL 代码外，所有解释和说明使用中文。

## 多表 JOIN 策略（非常重要！）

当用户的问题涉及多个概念（如"某实验的工艺参数"、"某材料的催化性能"、"某工艺的循环寿命"），
很可能需要跨表 JOIN。请遵循以下步骤：

### 第一步：识别需要关联的表
- 阅读 Schema 开头的「表关联关系」部分（如提供），了解哪些列是外键可以 JOIN
- 查看每张表的描述（中文说明），判断哪些表与用户问题相关
- 标注了「← FK」的列是最可靠的 JOIN 条件，优先使用

### 第二步：确定 JOIN 方式
- **INNER JOIN**: 当用户关注的是"有完整关联数据"的记录时（最常用）
- **LEFT JOIN**: 当主表记录即使没有关联数据也要保留时
  - 示例："统计每种工艺的循环测试次数（没有测试数据的计 0 次）"→ LEFT JOIN + COUNT
  - 示例："统计每种材料的平均催化性能" → INNER JOIN（只关心有数据的）
- 多个 LEFT JOIN 连续使用不会丢失主表数据，适合做"以某表为主，补充其他表信息"

### 第三步：选择 JOIN 条件
- 常见的列名模式：`xxx_id` → 对应另一张表的 `id` 列
  - 例：`experiments.process_id` → JOIN `process.id`
- 如果 Schema 中标注了关系，直接使用标注的列对
- 如果用户问题暗示了某种关联但 Schema 中没找到，请诚实告知

### 第四步：多表 JOIN 的性能提示
- JOIN 的顺序：先 JOIN 数据量小的表，再 JOIN 大表
- 在 WHERE 条件中尽早过滤，减少 JOIN 的数据量
- 多表 JOIN 时给每张表使用简短别名（e.g., e, p, c）提高可读性
- 聚合查询时，GROUP BY 需要包含所有非聚合的 SELECT 列

## SQL 编写规范

- 查询大表时尽量使用索引列作为过滤条件
- 对聚合查询使用适当的 GROUP BY 和 HAVING
- 结果集过大时建议加 LIMIT
- 使用 COALESCE 处理可能为 NULL 的列（LEFT JOIN 时主表列可能为 NULL）
- JOIN 时明确指定连接条件，避免笛卡尔积
- 对时间/日期列使用适当的类型转换函数
- 多表查询时，SELECT 中的列名建议使用表别名前缀，避免歧义
- 需要对多张结构相似的同级表（通过同一外键关联主表，如各实验子表）做统计时，
  优先使用扁平写法：每张表一行 `SELECT 常量 AS 类型, COUNT(*) FROM 表名`，再用 UNION ALL 合并；
  不要把所有表 UNION 成大子查询后再 JOIN 主表——SQL 过长会导致输出被截断而执行失败
"""

# ============================================================
#  Few-Shot 示例（放在 user prompt 中作为参考）
# ============================================================

FEW_SHOT_EXAMPLES = """
## 参考示例

### 示例 1（单表聚合 — 统计特例值）
用户问题: DSC 实验中最高的峰值温度是多少？
Schema:
Table dsc: DSC 差示扫描量热
  id integer
  sample_name text
  peak_temp numeric
  onset_temp numeric
  heating_rate numeric
  activation_energy numeric
  created_at timestamp

输出:
INTENT: data
```sql
SELECT MAX(peak_temp) AS max_peak_temp
FROM dsc
WHERE peak_temp IS NOT NULL;
```
说明: 用户想知道统计特例值，判为 data。用 MAX 聚合只返回单行统计结果，不返回任何明细记录。

### 示例 2（两表 JOIN — 单行聚合统计）
用户问题: 所有循环测试中最高的循环圈数和最高的初始容量是多少？
Schema:
## 表关联关系
  ● `cycle`.process_id → `process`.id (high 置信度)

Table process: 工艺主表
  id integer
  process_type text
  doi text
Table cycle: 循环寿命测试
  id integer
  process_id integer ← FK
  temperature numeric
  pressure numeric
  initial_capacity numeric
  final_capacity numeric
  cycle_count integer

输出:
INTENT: data
```sql
SELECT MAX(c.cycle_count) AS max_cycle_count,
       MAX(c.initial_capacity) AS max_initial_capacity
FROM process p
INNER JOIN cycle c ON c.process_id = p.id
WHERE c.cycle_count IS NOT NULL;
```
说明: 通过 process_id 将工艺主表与循环测试表关联后整体聚合，只返回一行两列的统计特例值。

### 示例 3（试图批量获取数据 → 拒绝提醒）
用户问题: 列出所有工艺及其对应的催化实验和循环测试数据（没有的也要列出）
Schema:
## 表关联关系
  ● `catalysis`.process_id → `process`.id (high 置信度)
  ● `cycle`.process_id → `process`.id (high 置信度)

Table process: 工艺主表
  id integer
  process_type text
  doi text
Table catalysis: 催化改性实验
  id integer
  process_id integer ← FK
  catalyst_name text
Table cycle: 循环寿命测试
  id integer
  process_id integer ← FK
  cycle_count integer

输出:
INTENT: chat
抱歉，无法进行批量操作。问数模式仅支持查询最大值、最小值、平均值等单行统计特例值。你可以试试问我"循环圈数的最大值是多少"或"循环测试的总记录数"。
说明: 用户试图获取整段明细记录（多行结果），违反问数模式的数据安全限制，判为 chat 并给出拒绝提醒与替代建议，不生成 SQL。

### 示例 4（多表统计 — 单行多列）
用户问题: 数据库中共有多少条循环测试记录和多少条催化实验记录？
Schema:
## 表关联关系
  ● `alloying`.process_id → `process`.id (high 置信度)
  ● `cycle`.process_id → `process`.id (high 置信度)
  ● `catalysis`.process_id → `process`.id (high 置信度)

Table process: 工艺主表
  id integer
  process_type text
  doi text
Table alloying: 合金制备实验
  id integer
  process_id integer ← FK
  alloy_name text
  milling_time numeric
Table cycle: 循环寿命测试
  id integer
  process_id integer ← FK
  cycle_count integer
Table catalysis: 催化改性实验
  id integer
  process_id integer ← FK
  catalyst_name text

输出:
INTENT: data
```sql
SELECT (SELECT COUNT(*) FROM cycle) AS cycle_test_count,
       (SELECT COUNT(DISTINCT process_id) FROM cycle) AS cycle_process_count,
       (SELECT COUNT(*) FROM catalysis) AS catalysis_test_count;
```
说明: 用标量子查询分别统计各表的记录数，多个统计值合并为一行输出，符合问数模式的单行限制。

### 示例 5（绘图意图）
用户问题: 画一张对比各种工艺类型平均循环寿命的柱状图
Schema:
Table process: 工艺主表
  id integer
  process_type text
Table cycle: 循环寿命测试
  id integer
  process_id integer ← FK
  cycle_count integer

输出:
INTENT: chart
```sql
SELECT p.process_type, ROUND(AVG(c.cycle_count), 2) AS avg_cycle_count
FROM process p
INNER JOIN cycle c ON c.process_id = p.id
WHERE p.process_type IS NOT NULL AND c.cycle_count IS NOT NULL
GROUP BY p.process_type
ORDER BY avg_cycle_count DESC;
```
说明: 用户明确要求绘图，判为 chart。聚合出绘图所需的分类 + 数值两列即可。

### 示例 6（闲聊/超范围意图）
用户问题: 你好，今天天气怎么样？
Schema:
Table dsc: DSC 差示扫描量热
  id integer

输出:
INTENT: chat
你好！我是数据库助手，只能帮你查询和解读数据库中的数据，比如 DSC 实验记录。关于天气的问题我无法回答，你可以试试问我"数据库里有多少条实验记录"。
"""

# ============================================================
#  图表自动推荐
# ============================================================

# 饼图分类数上限（超过则切片过多，视觉不可读）
PIE_MAX_CATEGORIES = 15


# ============================================================
#  Self-Correction Prompt（SQL 执行失败时使用）
# ============================================================

CORRECTION_PROMPT_TEMPLATE = """你之前为以下问题生成了 SQL，但执行时发生了错误。请分析错误原因并修正 SQL。

## 原始问题
{user_query}

## 原始 SQL（执行失败）
```sql
{failed_sql}
```

## 数据库返回的错误信息
{error_message}

## 纠错指南
1. 分析错误原因：
   - 语法错误 → 检查 SQL 关键字、括号、引号
   - 列名不存在 → 列名是否在 Schema 中存在？注意 JOIN 后的列名歧义（需加表别名前缀）
   - 类型不匹配 → 检查 WHERE 条件中比较值的类型是否正确
   - 表不存在 → 表名是否与 Schema 一致？查看 FROM/JOIN 子句
   - 歧义错误 → 多表 JOIN 时列名重复，需要用 `表名.列名` 或别名限定
   - 聚合错误 → GROUP BY 是否包含所有非聚合的 SELECT 列？
2. 根据下方 Schema 重新生成正确的 SQL
3. 如果是 JOIN 条件错误，仔细查看 Schema 中的「表关联关系」和 ← FK 标注
4. 必须输出**完整的修正后 SQL**（放在 ```sql ... ``` 代码块内），不要只给需要修改的片段或某一行
5. 只输出一个 SQL 代码块和一句简短说明，不要长篇分析
6. 如果无法修正，请在文本中说明原因

## 数据库 Schema
{schema_summary}

请修正 SQL:"""

# ============================================================
#  Prompt 构建函数
# ============================================================

def build_system_prompt(lang: str = "zh") -> str:
    """返回 system prompt（不含 schema，schema 动态注入 user prompt）。

    lang 控制说明文字语言：zh=中文（默认），en=英文界面时说明文字用英文。
    """
    if lang == "en":
        return SYSTEM_PROMPT.replace(
            "6. **中文回复**: 除 SQL 代码外，所有解释和说明使用中文。",
            "6. **Language**: All explanations and chat replies must be in English; only SQL code stays as-is.",
        )
    return SYSTEM_PROMPT


def _count_tables_in_schema(schema_summary: str) -> int:
    """统计 schema 文本中的表数量（用于决定是否启用多表推理提示）。"""
    import re
    return len(re.findall(r"^Table\s+\S+", schema_summary, re.MULTILINE))


def build_prompt(
    schema_summary: str,
    chat_history: list[dict] | None,
    user_query: str,
    include_few_shot: bool = True,
) -> str:
    """构建完整的 Text-to-SQL user prompt。

    Args:
        schema_summary: 裁剪后的数据库 schema 文本
        chat_history: 最近 N 轮对话历史，每项 {"role": "user"/"assistant", "content": "..."}
        user_query: 当前用户输入
        include_few_shot: 是否附加 few-shot 示例

    Returns:
        完整的 user prompt 字符串（不含 system prompt）
    """
    parts: list[str] = []
    table_count = _count_tables_in_schema(schema_summary)

    # Schema
    parts.append(f"## 数据库 Schema\n{schema_summary}")

    # Few-shot 示例
    if include_few_shot:
        parts.append(FEW_SHOT_EXAMPLES)

    # 对话历史（最多取最近 MAX_CONTEXT_MESSAGES 条，含上一轮的 SQL），供 LLM 多轮纠错使用
    if chat_history:
        history_lines: list[str] = []
        for msg in chat_history[-MAX_CONTEXT_MESSAGES:]:
            role_label = "用户" if msg.get("role") == "user" else "助手"
            content = msg.get("content", "")
            line = f"{role_label}: {content}"
            sql = msg.get("sql")
            if sql:
                line += f"\n[上一次执行的 SQL]\n```sql\n{sql}\n```"
            history_lines.append(line)
        if history_lines:
            parts.append(f"## 对话历史\n" + "\n".join(history_lines))

    # 当前问题 + 多表推理引导
    question_block = f"## 当前问题\n{user_query}"

    if table_count >= 3:
        question_block += (
            "\n\n"
            "请先思考以下问题（无需输出），再生成 SQL：\n"
            "1. 用户的问题涉及哪些概念？哪些表包含这些概念的数据？\n"
            "2. 这些表之间如何关联？（查看 Schema 中的 ← FK 标注和表关联关系）\n"
            "3. 应该用 INNER JOIN 还是 LEFT JOIN？\n"
            "4. 聚合和排序是否合理？\n"
            "\n"
            "然后直接输出最终的 SQL。"
        )
    else:
        question_block += "\n请生成 SQL:"

    parts.append(question_block)

    return "\n\n".join(parts)


def build_correction_prompt(
    user_query: str,
    failed_sql: str,
    error_message: str,
    schema_summary: str,
) -> str:
    """构建 SQL 纠错 prompt（Self-Correction 用）。

    Args:
        user_query: 用户的原始问题
        failed_sql: 执行失败的 SQL
        error_message: 数据库返回的错误信息
        schema_summary: 数据库 schema 文本

    Returns:
        完整的纠错 user prompt
    """
    return CORRECTION_PROMPT_TEMPLATE.format(
        user_query=user_query,
        failed_sql=failed_sql,
        error_message=error_message,
        schema_summary=schema_summary,
    )


def build_chart_recommendation_prompt(
    user_query: str,
    sql: str,
    columns: list[str],
    row_count: int,
    column_info: str = "",
) -> str:
    """构建图表推荐 prompt（用于 LLM 自动建议图表类型和坐标轴）。

    Args:
        user_query: 用户原始问题
        sql: 已执行的 SQL
        columns: 结果集的列名列表
        row_count: 结果行数
        column_info: 列信息摘要（列名 + 类型 + 唯一值数），帮助 LLM 判断坐标轴是否合理

    Returns:
        图表推荐 prompt
    """
    return f"""根据以下查询信息，推荐最合适的图表配置。

## 用户问题
{user_query}

## 执行的 SQL
```sql
{sql}
```

## 结果集信息
- 行数: {row_count}
- 列信息（列名, 类型, 唯一值数）:
{column_info or ', '.join(columns)}

## 要求
请用以下 JSON 格式输出（不要其他内容）:
```json
{{"chart_type": "line|area|bar|scatter|pie|histogram",
 "x_col": "列名（histogram 时填数值列名）",
 "y_col": "列名（histogram 时留空字符串）",
 "reason": "推荐理由（中文，一句话）"}}
```

## 图表类型选择指南
- line: 时间/序号趋势（X 为时间或有序类别，Y 为数值）
- area: 累计量/趋势幅度（同 line，强调体量感）
- bar: 分类对比（X 为类别，Y 为数值）
- scatter: 双数值列相关性（X、Y 都应为数值）
- pie: 占比/比例数据（X 为类别，Y 为数值）
- histogram: 单个数值列的分布/区间集中情况（x_col 填该数值列，y_col 留空）

## 硬性约束
1. x_col 和 y_col 必须是上面列信息中真实存在的列名
2. 除 pie 和 histogram 外，y_col 必须是"数值"类型列
3. pie 的 x_col 唯一值数不能超过 {PIE_MAX_CATEGORIES} 个
4. 除 histogram 外，x_col 与 y_col 不能相同
5. 用户问题关注"分布""集中在什么范围""区间"时优先 histogram
"""


