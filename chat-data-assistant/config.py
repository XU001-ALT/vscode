import os
from pathlib import Path
from dotenv import load_dotenv

# 加载.env文件（本地开发用）
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)


def _get(key: str, default: str = "") -> str:
    """优先从 Streamlit secrets 读取，其次从环境变量读取"""
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)


class Config:
    """配置管理类，优先从 Streamlit secrets 读取，其次从环境变量读取"""
    
    # 数据库配置
    DB_HOST: str = _get("DB_HOST", "localhost")
    DB_PORT: int = int(_get("DB_PORT", "5432"))
    DB_NAME: str = _get("DB_NAME", "your_db")
    DB_USER: str = _get("DB_USER", "read_only")
    DB_PASSWORD: str = _get("DB_PASSWORD", "")
    
    # LLM配置
    LLM_API_KEY: str = _get("LLM_API_KEY", "")
    LLM_PROVIDER: str = _get("LLM_PROVIDER", "openai")
    LLM_BASE_URL: str = _get("LLM_BASE_URL", "")
    LLM_MODEL: str = _get("LLM_MODEL", "")  # 空字符串表示自动选择 (openai→gpt-4o-mini, deepseek→deepseek-v4-flash)
    LLM_TEMPERATURE: float = float(_get("LLM_TEMPERATURE", "0.2"))
    LLM_MAX_TOKENS: int = int(_get("LLM_MAX_TOKENS", "2048"))  # SQL 生成最大 token 数
    
    # 调试开关：为 True 时把实际执行的 SQL 写入 logs/sql_debug.log（仅服务端可见，界面不展示）
    DEBUG_SQL: bool = _get("DEBUG_SQL", "false").lower() in ("true", "1", "yes")

    # AI 文字解读开关（问数模式）：开启后"想知道数据情况"类问题会把查询结果
    # 摘要发送给所配 LLM 服务生成文字结论。关闭则问数模式仅返回表格。
    ENABLE_AI_SUMMARY: bool = _get("ENABLE_AI_SUMMARY", "true").lower() in ("true", "1", "yes")
    
    @classmethod
    def validate_db(cls) -> list[str]:
        """验证数据库配置"""
        errors = []
        if not cls.DB_PASSWORD:
            errors.append("DB_PASSWORD 未设置")
        if not (1 <= cls.DB_PORT <= 65535):
            errors.append(f"DB_PORT 端口号无效: {cls.DB_PORT}")
        if not cls.DB_NAME or not cls.DB_NAME.strip():
            errors.append("DB_NAME 不能为空")
        if not cls.DB_HOST or not cls.DB_HOST.strip():
            errors.append("DB_HOST 不能为空")
        return errors
    
    @classmethod
    def validate_llm(cls) -> list[str]:
        """验证LLM配置"""
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY 未设置")
        valid_providers = ["openai", "deepseek", "anthropic", "azure", "local"]
        provider = cls.LLM_PROVIDER.strip().lower().replace(" ", "")
        if provider not in valid_providers:
            errors.append(f"LLM_PROVIDER 无效: {cls.LLM_PROVIDER}，支持: {', '.join(valid_providers)}")
        return errors
    
    @classmethod
    def validate(cls) -> list[str]:
        """验证所有配置"""
        return cls.validate_db() + cls.validate_llm()
    
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
