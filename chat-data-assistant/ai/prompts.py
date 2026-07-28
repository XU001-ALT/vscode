"""
Prompt 工程模块：System Prompt、Few-shot 示例、输出约束、纠错指令。

设计原则:
- 角色明确：PostgreSQL 专家，只生成 SELECT 查询
- 上下文限定：严格基于提供的 schema 回答问题
- Few-shot 学习：提供 2 个示例展示期望的输入/输出
- 冷启动策略：不知道答案时建议下一步操作
- 输出格式：SQL 必须用 ```sql 代码块包裹，便于解析
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

## SQL 编写规范

- 查询大表时尽量使用索引列作为过滤条件
- 对聚合查询使用适当的 GROUP BY 和 HAVING
- 结果集过大时建议加 LIMIT
- 使用 COALESCE 处理可能为 NULL 的列
- JOIN 时明确指定连接条件，避免笛卡尔积
- 对时间/日期列使用适当的类型转换函数
"""

# ============================================================
#  Few-Shot 示例（放在 user prompt 中作为参考）
# ============================================================

FEW_SHOT_EXAMPLES = """
## 参考示例

### 示例 1
用户问题: 查询脱氢实验中起始温度大于 500°C 的所有记录
Schema:
Table experiments:
  id integer
  sample_name text
  start_temp numeric
  end_temp numeric
  hydrogen_release numeric
  created_at timestamp

输出:
```sql
SELECT id, sample_name, start_temp, end_temp, hydrogen_release
FROM experiments
WHERE start_temp > 500
ORDER BY start_temp DESC
LIMIT 100;
```
说明: 筛选起始温度大于 500 的实验记录，按起始温度降序排列。

### 示例 2
用户问题: 统计每种材料的平均氢释放量
Schema:
Table experiments:
  id integer
  sample_name text
  material_type text
  hydrogen_release numeric
  created_at timestamp

输出:
```sql
SELECT material_type,
       COUNT(*) AS sample_count,
       ROUND(AVG(hydrogen_release), 2) AS avg_hydrogen_release
FROM experiments
WHERE hydrogen_release IS NOT NULL
GROUP BY material_type
ORDER BY avg_hydrogen_release DESC;
```
说明: 按材料类型分组统计平均氢释放量，排除空值，按平均值降序排列。
"""

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

## 要求
1. 分析错误原因（语法错误/列名不存在/类型不匹配/表不存在/权限问题等）
2. 根据下方 Schema 重新生成正确的 SQL
3. SQL 放在 ```sql ... ``` 代码块内
4. 如果是 Schema 中不存在的列或表，请诚实说明并建议替代方案
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
            history_lines.append(f"{role_label}: {content}")
        if history_lines:
            parts.append(f"## 对话历史\n" + "\n".join(history_lines))

    # 当前问题
    parts.append(f"## 当前问题\n{user_query}\n请生成 SQL:")

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
) -> str:
    """构建图表推荐 prompt（用于 LLM 自动建议图表类型和坐标轴）。

    Args:
        user_query: 用户原始问题
        sql: 已执行的 SQL
        columns: 结果集的列名列表
        row_count: 结果行数

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
- 列名: {', '.join(columns)}
- 行数: {row_count}

## 要求
请用以下 JSON 格式输出（不要其他内容）:
```json
{{"chart_type": "line|bar|scatter|pie",
 "x_col": "列名",
 "y_col": "列名",
 "reason": "推荐理由（中文，一句话）"}}
```
图表类型选择指南:
- line: 趋势/时间序列数据
- bar: 分类对比数据
- scatter: 双数值列的相关性分析
- pie: 占比/比例数据（类别不超过 10 个）
"""
