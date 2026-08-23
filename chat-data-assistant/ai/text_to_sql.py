"""
Text-to-SQL 核心模块：将自然语言转为可执行 SQL，并支持 Self-Correction 纠错循环。

流程:
    用户问题 + Schema + 对话历史
        → LLM 生成回复（首行 INTENT: chart|data|chat 意图标记 + SQL）
        → 解析意图（缺省按 chart，保持旧行为）
        → chat: 直接返回说明文字，不生成/执行 SQL
        → chart/data: SQL 安全校验 → 执行 (db.executor)
        → 成功 → 返回 DataFrame
        → 失败 → 构建纠错 prompt → LLM 修正 → 重试 (最多 2 次)
"""
import re
from typing import NamedTuple

from db.exceptions import DB_BUSY_MARKER

from .llm_client import call_llm, call_llm_raw, _normalize_response_text
from .prompts import build_system_prompt, build_prompt, build_correction_prompt
from .sql_guard import validate_sql

# 最大纠错重试次数
MAX_CORRECTION_RETRIES = 2
# 纠错时允许模型输出更长（含原因分析后再给 SQL，避免被截断）
CORRECTION_MAX_TOKENS = 4096
# 多表场景首次生成时的 token 数（JOIN + 说明文字更长）
MULTI_TABLE_MAX_TOKENS = 3072

# 意图标记解析（LLM 回复首行：INTENT: chart|data|chat）
_INTENT_RE = re.compile(r"^\s*INTENT:\s*(chart|data|chat)\s*$", re.IGNORECASE | re.MULTILINE)


class QueryOutcome(NamedTuple):
    """一次查询的完整结果。

    Attributes:
        sql: 实际执行的 SQL（chat 意图时为空字符串）
        df: 查询结果 DataFrame（无执行或失败时为 None）
        error: 错误信息（成功时为 None）
        intent: 解析出的意图 "chart" / "data" / "chat"
        message: chat 意图时模型的说明文字，其余意图为 None
    """
    sql: str
    df: object | None
    error: str | None
    intent: str
    message: str | None


def extract_intent(reply_text: str) -> str:
    """从 LLM 原始回复中解析意图标记；未标注或缺省时按 chart（与旧版行为一致）。"""
    m = _INTENT_RE.search(reply_text or "")
    return m.group(1).lower() if m else "chart"


def _clean_chat_message(reply_text: str) -> str:
    """提取 chat 意图的说明文字：去掉意图标记行与代码围栏。"""
    lines = []
    in_fence = False
    for ln in (reply_text or "").splitlines():
        if re.match(r"^\s*INTENT:", ln, re.IGNORECASE):
            continue
        if ln.strip().startswith("```"):
            in_fence = not in_fence  # 跳过围栏行本身，保留其中文字
            continue
        if not in_fence:
            lines.append(ln)
    cleaned = "\n".join(lines).strip()
    return cleaned or "（模型未返回有效回应，请换个问法试试。）"


def _count_tables_in_schema(schema_summary: str) -> int:
    """统计 schema 文本中的表数量。"""
    return len(re.findall(r"^Table\s+\S+", schema_summary, re.MULTILINE))


def _extract_sql_text(text: str) -> str:
    """从 LLM 回复中提取 SQL（call_llm 已做归一化，这里做最终 strip）。"""
    return text.strip()


def _no_valid_sql_message(err_msg: str, attempt: int = 0) -> str:
    """LLM 未生成合法 SQL 时的友好提示（区别于真正的安全拦截）"""
    reason = "模型未返回以 SELECT/WITH 开头的 SQL" if "只读" in err_msg else err_msg
    if attempt:
        return (
            f"LLM 纠错 {attempt} 次后仍未生成合法 SQL（{reason}）。"
            f"请换个问法，或确认问题在已加载的表结构范围内。"
        )
    return (
        f"LLM 重试后仍未生成合法 SQL（{reason}）。"
        f"请换个问法，或确认问题在已加载的表结构范围内。"
    )


def to_sql(
    schema_summary: str,
    chat_history: list[dict] | None,
    user_query: str,
    llm_cfg: dict | None = None,
) -> str:
    """生成 SQL（单次调用，不做纠错）。

    Args:
        schema_summary: 裁剪后的数据库 schema
        chat_history: 对话历史
        user_query: 用户问题
        llm_cfg: 会话级 LLM 配置（见 call_llm）

    Returns:
        校验通过的 SQL 字符串

    Raises:
        ValueError: SQL 校验失败
        RuntimeError: LLM 调用失败
    """
    system = build_system_prompt()
    prompt = build_prompt(schema_summary, chat_history, user_query)
    raw_sql = call_llm(prompt, system=system, llm_cfg=llm_cfg)
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
    llm_cfg: dict | None = None,
    lang: str = "zh",
) -> QueryOutcome:
    """生成 SQL 并执行，失败时自动纠错重试；chat 意图直接返回说明文字。

    Args:
        schema_summary: 裁剪后的数据库 schema
        chat_history: 对话历史
        user_query: 用户问题
        execute_fn: SQL 执行函数，签名为 (sql: str) -> (pd.DataFrame | None, str | None)
                    即 execute_sql_safe 的签名
        llm_cfg: 会话级 LLM 配置（见 call_llm）
        lang: 说明文字语言（"zh"/"en"，影响 chat 回应与纠错提示）

    Returns:
        QueryOutcome(sql, df, error, intent, message)
    """
    system = build_system_prompt(lang=lang)
    prompt = build_prompt(schema_summary, chat_history, user_query)

    # 多表场景分配更多 token（JOIN SQL + 说明文字更长）
    table_count = _count_tables_in_schema(schema_summary)
    first_attempt_tokens = MULTI_TABLE_MAX_TOKENS if table_count >= 3 else 2048

    # 第一次尝试（用原始回复：INTENT 标记行在代码块外，call_llm 的归一化会把它剥掉）
    raw = call_llm_raw(prompt, system=system, max_tokens=first_attempt_tokens,
                       llm_cfg=llm_cfg)
    intent = extract_intent(raw)

    # chat 意图：不生成/执行 SQL，直接返回说明文字，避免空跑校验与纠错循环
    if intent == "chat":
        return QueryOutcome(sql="", df=None, error=None,
                            intent="chat", message=_clean_chat_message(raw))

    sql = _normalize_response_text(raw)

    valid, err_msg = validate_sql(sql)
    if not valid:
        # LLM 没直接给出合法 SQL（可能只回了文字说明），让 LLM 修正一次
        prompt = build_correction_prompt(
            user_query=user_query,
            failed_sql=sql or "(空)",
            error_message=f"未生成合法 SQL: {err_msg}",
            schema_summary=schema_summary,
        )
        raw = call_llm_raw(prompt, system=system, max_tokens=CORRECTION_MAX_TOKENS,
                           llm_cfg=llm_cfg)
        sql = _normalize_response_text(raw)
        valid2, err_msg2 = validate_sql(sql)
        if not valid2:
            return QueryOutcome(sql=sql, df=None,
                                error=_no_valid_sql_message(err_msg2),
                                intent=intent, message=None)

    # 执行 SQL
    df, exec_err = execute_fn(sql)
    if exec_err is None:
        return QueryOutcome(sql=sql, df=df, error=None, intent=intent, message=None)
    if DB_BUSY_MARKER in exec_err:
        # 数据库过载（连接池满）：纠错重试无法解决，快速失败避免拖长响应
        return QueryOutcome(sql=sql, df=None, error=exec_err,
                            intent=intent, message=None)

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
        raw_corrected = call_llm_raw(correction_prompt, system=system,
                                     max_tokens=CORRECTION_MAX_TOKENS, llm_cfg=llm_cfg)
        corrected_sql = _normalize_response_text(raw_corrected)

        valid, err_msg = validate_sql(corrected_sql)
        if not valid:
            return QueryOutcome(sql=corrected_sql, df=None,
                                error=_no_valid_sql_message(err_msg, attempt + 1),
                                intent=intent, message=None)

        df, exec_err = execute_fn(corrected_sql)
        if exec_err is None:
            return QueryOutcome(sql=corrected_sql, df=df, error=None,
                                intent=intent, message=None)
        if DB_BUSY_MARKER in exec_err:
            return QueryOutcome(sql=corrected_sql, df=None, error=exec_err,
                                intent=intent, message=None)

        current_sql = corrected_sql
        current_error = exec_err

    return QueryOutcome(sql=current_sql, df=None,
                        error=f"SQL 执行失败（已重试 {MAX_CORRECTION_RETRIES} 次）: {current_error}",
                        intent=intent, message=None)

