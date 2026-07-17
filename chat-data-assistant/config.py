# 配置占位符：请在部署时替换为真实值或通过环境变量注入
CONFIG = {
    "DB": {
        "HOST": "localhost",
        "PORT": 5432,
        "NAME": "your_db",
        "USER": "read_only",
        "PASSWORD": "read-only",
    },
    "LLM": {
        "API_KEY": "",
        "PROVIDER": "openai",
    }
}
