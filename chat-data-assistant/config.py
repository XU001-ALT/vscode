import os
from pathlib import Path
from dotenv import load_dotenv

# 加载.env文件
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)


class Config:
    """配置管理类，优先从环境变量读取"""
    
    # 数据库配置
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "your_db")
    DB_USER: str = os.getenv("DB_USER", "read_only")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    
    # LLM配置
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")
    
    @classmethod
    def validate(cls) -> list[str]:
        """验证必要配置，返回缺失的配置项列表"""
        errors = []
        
        # 必填字段验证
        if not cls.DB_PASSWORD:
            errors.append("DB_PASSWORD 未设置")
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY 未设置")
        
        # 格式验证
        if not (1 <= cls.DB_PORT <= 65535):
            errors.append(f"DB_PORT 端口号无效: {cls.DB_PORT}")
        
        if not cls.DB_NAME or not cls.DB_NAME.strip():
            errors.append("DB_NAME 不能为空")
        
        if not cls.DB_HOST or not cls.DB_HOST.strip():
            errors.append("DB_HOST 不能为空")
        
        # LLM Provider验证
        valid_providers = ["openai", "anthropic", "azure", "local"]
        if cls.LLM_PROVIDER.lower() not in valid_providers:
            errors.append(f"LLM_PROVIDER 无效: {cls.LLM_PROVIDER}，支持: {', '.join(valid_providers)}")
        
        return errors
    
    @classmethod
    def is_valid(cls) -> bool:
        """检查配置是否有效"""
        return len(cls.validate()) == 0
    
    @classmethod
    def get_db_url(cls) -> str:
        """获取数据库连接URL"""
        return f"postgresql+psycopg2://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"


# 全局配置实例
config = Config()
