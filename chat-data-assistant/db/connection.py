from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config


def make_engine(host: str = None, port: int = None, dbname: str = None, 
                user: str = None, password: str = None) -> Engine:
    """
    创建数据库引擎
    
    如果不提供参数，使用config中的配置
    """
    # 验证配置
    errors = config.validate()
    if errors:
        raise ValueError(f"配置错误: {', '.join(errors)}")
    
    # 使用传入参数或配置
    db_url = f"postgresql+psycopg2://{user or config.DB_USER}:{password or config.DB_PASSWORD}@{host or config.DB_HOST}:{port or config.DB_PORT}/{dbname or config.DB_NAME}"
    engine = create_engine(db_url, pool_pre_ping=True)
    return engine


def get_engine() -> Engine:
    """使用配置创建引擎的便捷函数"""
    return make_engine()
