# Chat Data 部署文档

新版界面为 **前后端完全分离**架构：FastAPI 只提供 `/api/*` 接口，前端为独立的静态站点。

```
浏览器 ──→ 前端（Nginx/CDN/独立服务器）
               │
               ├── 页面资源（HTML/JS/CSS）
               │
               └── /api/* ──→ FastAPI:8000（后端接口）
```

> 注意：`streamlit run app.py` 运行的是旧版界面，与新架构互不影响，部署时无需安装启动旧版。

---

## 一、准备工作

| 项 | 要求 |
|----|------|
| Python | ≥ 3.11（服务器推荐 3.12 正式版） |
| Node.js | ≥ 20（构建前端时需要） |
| 网络 | 服务器需能访问目标 PostgreSQL（5432）与 LLM API（如 api.deepseek.com） |

## 二、配置 .env

`.env` 含密钥，不进 git，需手动创建：

```bash
cp .env.example .env
# 然后填写 DB_HOST / DB_NAME / DB_USER / DB_PASSWORD / LLM_API_KEY 等
```

## 三、部署后端

```bash
# 1. 获取代码
git clone <仓库地址> chat-data-assistant && cd chat-data-assistant

# 2. Python 环境
python -m venv venv
venv\Scripts\pip install -r requirements.txt      # Windows
# venv/bin/pip install -r requirements.txt        # Linux

# 3. 启动后端（只提供 API）
venv\Scripts\python -m uvicorn api.main:app --host 0.0.0.0 --port 8000    # Windows
# venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000       # Linux
```

## 四、部署前端（独立部署）

前端构建时通过 `VITE_API_BASE_URL` 指定后端地址，构建后可部署到任意静态服务器。

### 方式 A：Nginx（推荐生产环境）

```bash
# 1. 构建前端（指定后端地址）
cd frontend
cp .env.example .env
# 编辑 .env 设置 VITE_API_BASE_URL=http://你的后端IP:8000
npm install && npm run build

# 2. 部署 dist/ 到 Nginx
cp -r dist/* /var/www/chat-data/
```

Nginx 配置：

```nginx
server {
    listen 80;
    server_name your.domain.com;

    # 前端静态文件
    location / {
        root /var/www/chat-data;
        try_files $uri $uri/ /index.html;
    }

    # API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 方式 B：Vite preview（简单测试）

```bash
cd frontend
VITE_API_BASE_URL=http://你的后端IP:8000 npm run build
npm run preview  # 默认 4173 端口
```

### 方式 C：Docker（前后端分离）

```bash
# 后端
docker build -t chat-data-api .
docker run -d --env-file .env -p 8000:8000 --name chat-api chat-data-api

# 前端（构建时指定后端地址）
cd frontend
docker build --build-arg VITE_API_BASE_URL=http://你的后端IP:8000 -t chat-data-web .
docker run -d -p 80:80 --name chat-web chat-data-web
```

## 五、CORS 配置

后端通过环境变量 `CORS_ORIGINS` 控制允许的前端来源（逗号分隔）：

```bash
# .env
CORS_ORIGINS=http://your.domain.com,http://localhost:5173
```

不设置时默认允许 `localhost:5173/4173/8000`。

## 六、防火墙放行

- 后端服务器：放行 **8000** 端口入站（仅限前端服务器 IP 访问更安全）
- 前端服务器：放行 **80** 端口入站
- 应用服务器需能**出站**访问 PostgreSQL 5432 与 LLM API 地址

## 七、常见问题

| 现象 | 排查 |
|------|------|
| 页面打开但「数据库连接失败」 | `.env` 是否正确；应用服务器到 DB 的 5432 端口是否连通 |
| 提问报「LLM 相关错误」 | `.env` 的 `LLM_API_KEY` / `LLM_BASE_URL`；或在页面配置区填写 |
| 前端请求 403/跨域错误 | 后端 `CORS_ORIGINS` 是否包含前端域名 |
| 前端请求 404/连接拒绝 | `VITE_API_BASE_URL` 是否正确；后端服务是否在运行 |
| 只改了前端代码 | `cd frontend && npm run build` 后刷新即可，无需重启后端 |
