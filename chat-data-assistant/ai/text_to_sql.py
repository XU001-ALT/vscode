"""
Text-to-SQL 核心模块：将自然语言转为可执行 SQL，并支持 Self-Correction 纠错循环。

流程:
    用户问题 + Schema + 对话历史
        → LLM 生成 SQL
        → SQL 安全校验
        → 执行 (db.executor)
        → 成功 → 返回 DataFrame
        → 失败 → 构建纠错 prompt → LLM 修正 → 重试 (最多 2 次)
"""
from .llm_client import call_llm, call_llm_raw
from .prompts import build_system_prompt, build_prompt, build_correction_prompt
from .sql_guard import validate_sql

# 最大纠错重试次数
MAX_CORRECTION_RETRIES = 2


def _extract_sql_text(text: str) -> str:
    """从 LLM 回复中提取 SQL（call_llm 已做归一化，这里做最终 strip）。"""
    return text.strip()


def to_sql(
    schema_summary: str,
    chat_history: list[dict] | None,
    user_query: str,
) -> str:
    """生成 SQL（单次调用，不做纠错）。

    Args:
        schema_summary: 裁剪后的数据库 schema
        chat_history: 对话历史
        user_query: 用户问题

    Returns:
        校验通过的 SQL 字符串

    Raises:
        ValueError: SQL 校验失败
        RuntimeError: LLM 调用失败
    """
    system = build_system_prompt()
    prompt = build_prompt(schema_summary, chat_history, user_query)
    raw_sql = call_llm(prompt, system=system)
    sql = _extract_sql_text(raw_sql)

    valid, error = validate_sql(sql)
    if not valid:
        raise ValueError(f"LLM 生成的 SQL 校验失败：{error}\n{sql}")

    return sql


def to_sql_with_correction(
    schema_summary: str,
    chat_history: list[dict] | None,
    user_query: str,
    execute_fn,
) -> tuple[str, object, str | None]:
    """生成 SQL 并执行，失败时自动纠错重试。

    Args:
        schema_summary: 裁剪后的数据库 schema
        chat_history: 对话历史
        user_query: 用户问题
        execute_fn: SQL 执行函数，签名为 (sql: str) -> (pd.DataFrame | None, str | None)
                    即 execute_sql_safe 的签名

    Returns:
        (sql, df_or_none, error_or_none) 三元组
        - success: (sql_str, DataFrame, None)
        - failure: (last_sql_str, None, error_message)
    """
    system = build_system_prompt()
    prompt = build_prompt(schema_summary, chat_history, user_query)

    # 第一次尝试
    raw_sql = call_llm(prompt, system=system)
    sql = _extract_sql_text(raw_sql)

    valid, err_msg = validate_sql(sql)
    if not valid:
        # 安全校验失败，尝试让 LLM 修正
        prompt = build_correction_prompt(
            user_query=user_query,
            failed_sql=sql or "(空)",
            error_message=f"安全校验: {err_msg}",
            schema_summary=schema_summary,
        )
        raw_sql = call_llm_raw(prompt, system=system)
        sql = _extract_sql_text(raw_sql)
        valid2, err_msg2 = validate_sql(sql)
        if not valid2:
            return sql, None, f"SQL 安全校验失败（已重试）: {err_msg2}"

    # 执行 SQL
    df, exec_err = execute_fn(sql)
    if exec_err is None:
        return sql, df, None

    # Self-Correction 循环
    current_sql = sql
    current_error = exec_err
    for attempt in range(MAX_CORRECTION_RETRIES):
        correction_prompt = build_correction_prompt(
            user_query=user_query,
            failed_sql=current_sql,
            error_message=current_error,
            schema_summary=schema_summary,
        )
        raw_corrected = call_llm_raw(correction_prompt, system=system)
        corrected_sql = _extract_sql_text(raw_corrected)

        valid, err_msg = validate_sql(corrected_sql)
        if not valid:
            return corrected_sql, None, f"纠错后 SQL 校验失败 (第{attempt + 1}次): {err_msg}"

        df, exec_err = execute_fn(corrected_sql)
        if exec_err is None:
            return corrected_sql, df, None

        current_sql = corrected_sql
        current_error = exec_err

    return current_sql, None, f"SQL 执行失败（已重试 {MAX_CORRECTION_RETRIES} 次）: {current_error}"
