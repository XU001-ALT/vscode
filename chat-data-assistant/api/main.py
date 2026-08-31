"""Chat Data API 入口（前后端分离版）。

启动：
    venv\\Scripts\\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000
（必须在 chat-data-assistant 目录下运行）

本服务只提供 /api/* 接口，前端需独立部署（Nginx / CDN / Vite preview 等）。
前端通过环境变量 VITE_API_BASE_URL 指向本服务地址。
"""
import os
from contextlib import asynccontextmanager

from api import compat  # noqa: F401  必须最先导入：Python 3.14rc2 typing 兼容补丁
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core import bootstrap


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap.start()  # 后台线程连接数据库并自动拉取 schema，失败自动重试
    yield


app = FastAPI(title="Chat Data API", lifespan=lifespan)

# CORS 允许的前端来源，通过环境变量 CORS_ORIGINS 配置（逗号分隔）
# 默认允许常见开发端口；部署时按实际前端域名配置
_cors_raw = os.getenv("CORS_ORIGINS", "")
if _cors_raw.strip():
    _cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]
else:
    _cors_origins = [
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:4173", "http://127.0.0.1:4173",
        "http://localhost:8000", "http://127.0.0.1:8000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

from api.routes.config_api import router as config_router  # noqa: E402
from api.routes.query import router as query_router  # noqa: E402
from api.routes.schema_api import router as schema_router  # noqa: E402
from api.routes.system import router as system_router  # noqa: E402

app.include_router(system_router)
app.include_router(schema_router)
app.include_router(query_router)
app.include_router(config_router)
