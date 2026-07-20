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
