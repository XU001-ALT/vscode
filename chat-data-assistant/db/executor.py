import pandas as pd
from sqlalchemy import text
from db.connection import get_engine, get_connection
from db.exceptions import SQLExecutionError, SecurityError
import re

# 危险SQL关键字（用于简单安全校验）
DANGEROUS_KEYWORDS = [
    "DROP", "DELETE", "TRUNCATE", "ALTER", "INSERT", "UPDATE",
    "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
]

# 只读操作前缀
READONLY_PREFIXES = ["SELECT", "WITH", "EXPLAIN", "SHOW", "DESCRIBE", "DESC"]


def check_sql_safety(sql: str) -> None:
    """简单SQL安全校验"""
    sql_upper = sql.strip().upper()

    # 检查是否为空
    if not sql_upper:
        raise SecurityError("SQL语句不能为空")

    # 检查是否为只读操作
    is_readonly = any(sql_upper.startswith(p) for p in READONLY_PREFIXES)
    if not is_readonly:
        raise SecurityError(
            f"安全限制：仅允许SELECT/WITH/EXPLAIN等只读查询，"
            f"不允许包含: {', '.join(DANGEROUS_KEYWORDS)}"
        )


def execute_sql(
    sql: str,
    timeout: int = 30,
    max_rows: int = 1000,
) -> pd.DataFrame:
    """
    执行SQL查询，返回DataFrame

    Args:
        sql: SQL语句
        timeout: 查询超时（秒）
        max_rows: 最大返回行数
    """
    check_sql_safety(sql)

    try:
        engine = get_engine()
        df = pd.read_sql(text(sql), engine)
        if len(df) > max_rows:
            df = df.head(max_rows)
        return df
    except SecurityError:
        raise
    except Exception as e:
        raise SQLExecutionError(f"SQL执行失败: {e}")


def execute_sql_safe(sql: str, max_rows: int = 1000) -> tuple[pd.DataFrame | None, str | None]:
    """
    安全执行SQL，返回 (DataFrame, 错误信息) 元组
    """
    try:
        df = execute_sql(sql, max_rows=max_rows)
        return df, None
    except Exception as e:
        return None, str(e)


def get_table_list() -> list[str]:
    """获取所有用户表名"""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        ))
        return [row[0] for row in result]


def get_table_schema(table_name: str) -> pd.DataFrame:
    """获取指定表的结构信息"""
    sql = f"""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = '{table_name}' AND table_schema = 'public'
        ORDER BY ordinal_position
    """
    return execute_sql(sql)


def fetch_full_schema() -> str:
    """从数据库自动拉取所有表的结构，返回文本摘要"""
    engine = get_engine()
    lines = []
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        ))
        tables = [row[0] for row in result]

        for table in tables:
            result = conn.execute(text(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                f"WHERE table_name = '{table}' AND table_schema = 'public' "
                "ORDER BY ordinal_position"
            ))
            cols = [f"  {row[0]} {row[1]}{' (nullable)' if row[2] == 'YES' else ''}" for row in result]
            lines.append(f"Table {table}:\n" + "\n".join(cols))

    return "\n\n".join(lines) if lines else "未找到任何表"
