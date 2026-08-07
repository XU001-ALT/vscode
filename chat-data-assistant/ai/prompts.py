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

# ============================================================
#  System Prompt（系统角色与行为约束）
# ============================================================

SYSTEM_PROMPT = """你是一名 PostgreSQL 数据库专家助手，专门负责将用户的自然语言问题转换为可执行的 SQL 查询。

## 核心规则（必须遵守）

1. **只读原则**: 只生成 SELECT、WITH (CTE)、EXPLAIN、SHOW、DESCRIBE 查询。绝对禁止 DROP、DELETE、TRUNCATE、ALTER、INSERT、UPDATE、CREATE、GRANT、REVOKE、EXECUTE 等写操作。
2. **Schema 限定**: 只使用下方 Schema 中列出的表和列。不允许臆造表名或列名。
3. **安全编码**: 字符串值使用单引号；LIKE 模式中百分号用单引号包裹；避免 SQL 注入。
4. **回答格式**: 每个回复中，SQL 必须放在 ```sql ... ``` 代码块内。如果问题不需要 SQL（如闲聊或澄清），则在文本中直接说明。
5. **冷启动**: 如果根据提供的 Schema 无法回答问题，请诚实地说"无法从当前数据库中找到相关数据"，并建议用户补充信息。
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
  - 示例："列出所有实验及其循环测试结果（没有测试的也要列出来）"→ LEFT JOIN
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
"""

# ============================================================
#  Few-Shot 示例（放在 user prompt 中作为参考）
# ============================================================

FEW_SHOT_EXAMPLES = """
## 参考示例

### 示例 1（单表查询）
用户问题: 查询起始温度大于 500°C 的所有 DSC 实验记录
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
```sql
SELECT id, sample_name, peak_temp, onset_temp, heating_rate, activation_energy
FROM dsc
WHERE onset_temp > 500
ORDER BY onset_temp DESC
LIMIT 100;
```
说明: 筛选起始温度大于 500°C 的 DSC 实验，按起始温度降序排列，限制返回 100 条。

### 示例 2（两表 JOIN — 通过外键关联）
用户问题: 查询每种工艺对应的循环寿命测试结果，需要工艺类型和循环圈数
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
```sql
SELECT p.process_type,
       c.temperature,
       c.pressure,
       c.initial_capacity,
       c.final_capacity,
       c.cycle_count,
       ROUND((c.final_capacity / NULLIF(c.initial_capacity, 0)) * 100, 2) AS capacity_retention_pct
FROM process p
INNER JOIN cycle c ON c.process_id = p.id
WHERE c.initial_capacity IS NOT NULL
ORDER BY c.cycle_count DESC
LIMIT 100;
```
说明: 通过 process_id 将工艺主表与循环测试表关联，计算容量保持率，按循环圈数排序。

### 示例 3（三表 LEFT JOIN — 以某表为主，补充多张关联表）
用户问题: 列出所有工艺及其对应的催化实验和循环测试数据（没有的也要列出工艺）
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
  particle_size numeric
  additive_amount numeric
Table cycle: 循环寿命测试
  id integer
  process_id integer ← FK
  temperature numeric
  cycle_count integer

输出:
```sql
SELECT p.id AS process_id,
       p.process_type,
       p.doi,
       cat.catalyst_name,
       cat.particle_size,
       COALESCE(cat.additive_amount, 0) AS additive_amount,
       cyc.temperature AS cycle_temperature,
       COALESCE(cyc.cycle_count, 0) AS cycle_count
FROM process p
LEFT JOIN catalysis cat ON cat.process_id = p.id
LEFT JOIN cycle cyc ON cyc.process_id = p.id
ORDER BY p.id
LIMIT 200;
```
说明: 以 process 为主表用 LEFT JOIN 保留所有工艺记录，没有催化/循环数据的列用 COALESCE 填充默认值。

### 示例 4（多表 JOIN + 聚合统计）
用户问题: 统计每种合金工艺的平均循环寿命和催化实验数量
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
```sql
SELECT p.process_type,
       a.alloy_name,
       COUNT(DISTINCT cyc.id) AS cycle_test_count,
       ROUND(AVG(cyc.cycle_count), 2) AS avg_cycle_count,
       COUNT(DISTINCT cat.id) AS catalysis_test_count
FROM process p
INNER JOIN alloying a ON a.process_id = p.id
LEFT JOIN cycle cyc ON cyc.process_id = p.id
LEFT JOIN catalysis cat ON cat.process_id = p.id
WHERE p.process_type IS NOT NULL
GROUP BY p.process_type, a.alloy_name
ORDER BY avg_cycle_count DESC
LIMIT 50;
```
说明: 四表联查，process → alloying 用 INNER JOIN（只统计有合金数据的），cycle/catalysis 用 LEFT JOIN（可能没有），用 COUNT(DISTINCT) 避免重复计数。
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
4. SQL 放在 ```sql ... ``` 代码块内
5. 如果无法修正，请在文本中说明原因

## 数据库 Schema
{schema_summary}

请修正 SQL:"""

# ============================================================
#  Prompt 构建函数
# ============================================================

def build_system_prompt() -> str:
    """返回纯 system prompt（不含 schema，schema 动态注入 user prompt）"""
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

    # 对话历史（最近若干轮，含上一轮的 SQL）
    if chat_history:
        history_lines: list[str] = []
        for msg in chat_history[-14:]:  # 最多保留最近 14 条消息
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
{{"chart_type": "line|bar|scatter|pie",
 "x_col": "列名",
 "y_col": "列名",
 "reason": "推荐理由（中文，一句话）"}}
```

## 图表类型选择指南
- line: 时间/序号趋势（X 为时间或有序类别，Y 为数值）
- bar: 分类对比（X 为类别，Y 为数值）
- scatter: 双数值列相关性（X、Y 都应为数值）
- pie: 占比/比例数据（X 为类别，Y 为数值）

## 硬性约束
1. x_col 和 y_col 必须是上面列信息中真实存在的列名
2. 除 pie 外，y_col 必须是"数值"类型列
3. pie 的 x_col 唯一值数不能超过 {PIE_MAX_CATEGORIES} 个
4. x_col 与 y_col 不能相同
"""

