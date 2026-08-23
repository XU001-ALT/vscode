# 数据库过载（连接池耗尽）错误标记。
# ai/text_to_sql 据此跳过无意义的 LLM 纠错重试；executor 负责抛出该标记。
DB_BUSY_MARKER = "连接池已满"


class DatabaseError(Exception):
    """数据库基础异常"""
    pass


class DatabaseConfigError(DatabaseError):
    """数据库配置错误"""
    pass


class DatabaseConnectionError(DatabaseError):
    """数据库连接失败"""
    pass


class SQLExecutionError(DatabaseError):
    """SQL执行错误"""
    pass


class SQLError(DatabaseError):
    """SQL语法或逻辑错误"""
    pass


class SecurityError(DatabaseError):
    """安全限制异常（如危险操作被拦截）"""
    pass
