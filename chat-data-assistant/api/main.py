"""Chat Data API 入口。

启动：
    venv\\Scripts\\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000
（必须在 chat-data-assistant 目录下运行）

开发模式下前端由 Vite 开发服务器托管（5173），通过代理访问 /api；
生产模式下若存在 frontend/dist 则直接由本服务托管静态文件。
"""
from contextlib import asynccontextmanager
from pathlib import Path

from api import compat  # noqa: F401  必须最先导入：Python 3.14rc2 typing 兼容补丁
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core import bootstrap


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap.start()  # 后台线程连接数据库并自动拉取 schema，失败自动重试
    yield


app = FastAPI(title="Chat Data API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:4173", "http://127.0.0.1:4173",
    ],
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

# 生产模式：托管前端构建产物（需在路由注册之后挂载）。
# index.html 每次都向服务器校验新鲜度（no-cache），避免更新后浏览器用旧页面
# 引用已被删除的旧 hash 资源；带 hash 的静态资源仍可长期缓存。
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")

    @app.middleware("http")
    async def no_cache_index(request, call_next):
        response = await call_next(request)
        if request.url.path in ("/", "/index.html"):
            response.headers["Cache-Control"] = "no-cache"
        return response
