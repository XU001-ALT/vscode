from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
import sys
from pathlib import Path
from contextlib import contextmanager

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config
from db.exceptions import DatabaseConnectionError, DatabaseConfigError


def make_engine(
    host: str = None,
    port: int = None,
    dbname: str = None,
    user: str = None,
    password: str = None,
    pool_size: int = 5,
    max_overflow: int = 10,
) -> Engine:
    """
    创建数据库引擎（带连接池）
    """
    errors = config.validate_db()
    if errors:
        raise DatabaseConfigError(f"数据库配置错误: {', '.join(errors)}")

    db_url = (
        f"postgresql+psycopg2://{user or config.DB_USER}:{password or config.DB_PASSWORD}"
        f"@{host or config.DB_HOST}:{port or config.DB_PORT}/{dbname or config.DB_NAME}"
    )

    engine = create_engine(
        db_url,
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    return engine


class DatabaseManager:
    """数据库连接管理器（单例）"""

    _instance = None
    _engine: Engine = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def connect(self) -> Engine:
        """获取或创建引擎"""
        if self._engine is None:
            self._engine = make_engine()
        return self._engine

    def close(self):
        """关闭引擎，释放连接池"""
        if self._engine:
            self._engine.dispose()
            self._engine = None

    def health_check(self) -> bool:
        """健康检查：测试数据库是否可达"""
        try:
            engine = self.connect()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def get_info(self) -> dict:
        """获取数据库基本信息"""
        engine = self.connect()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            result = conn.execute(text("SELECT current_database()"))
            db_name = result.scalar()
            result = conn.execute(text("SELECT current_user"))
            user = result.scalar()
        return {"version": version, "database": db_name, "user": user}


db_manager = DatabaseManager()


def get_engine() -> Engine:
    """便捷函数：获取引擎"""
    return db_manager.connect()


@contextmanager
def get_connection():
    """上下文管理器：获取数据库连接"""
    engine = get_engine()
    conn = engine.connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
