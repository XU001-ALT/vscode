# Chat Data 部署文档

新版界面为 **FastAPI（后端 API）+ React（前端）** 架构，构建后由 FastAPI 单进程同时托管 API 与前端静态页面，只需部署一个服务。

```
浏览器 ──→ http://服务器IP:8000
                │
           uvicorn (FastAPI)
            ├── /api/*   后端接口（查询 / Schema / 配置）
            └── /*       frontend/dist 前端静态页面
```

> 注意：`streamlit run app.py` 运行的是旧版界面，与新架构互不影响，部署时无需安装启动旧版。

---

## 一、准备工作

| 项 | 要求 |
|----|------|
| Python | ≥ 3.11（服务器推荐 3.12 正式版） |
| Node.js | ≥ 20（仅构建前端时需要；本地构建好拷贝 `dist/` 则不需要） |
| 网络 | 服务器需能访问目标 PostgreSQL（5432）与 LLM API（如 api.deepseek.com） |

## 二、配置 .env

`.env` 含密钥，不进 git，需手动创建：

```bash
cp .env.example .env
# 然后填写 DB_HOST / DB_NAME / DB_USER / DB_PASSWORD / LLM_API_KEY 等
```

## 三、方式 A：直接部署（最简单）

```bash
# 1. 获取代码
git clone <仓库地址> chat-data-assistant && cd chat-data-assistant

# 2. Python 环境
python -m venv venv
venv\Scripts\pip install -r requirements.txt      # Windows
# venv/bin/pip install -r requirements.txt        # Linux

# 3. 构建前端（二选一）
#   a) 服务器上构建：装 Node 后执行
cd frontend && npm install && npm run build && cd ..
#   b) 或本地构建后，把 frontend/dist 整个目录拷贝到服务器同路径

# 4. 启动
venv\Scripts\python -m uvicorn api.main:app --host 0.0.0.0 --port 8000    # Windows
# venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000       # Linux
```

Windows 下可直接双击 `start.bat`（自动检查 .env、按需构建前端并启动）。

访问 `http://服务器IP:8000` 即可使用。

## 四、方式 B：systemd 服务（Linux 生产推荐）

```bash
# 1. 按方式 A 完成代码放置、依赖安装、前端构建（假设目录 /opt/chat-data-assistant）

# 2. 安装服务
sudo cp deploy/chat-data.service /etc/systemd/system/
sudo nano /etc/systemd/system/chat-data.service   # 核对 WorkingDirectory/User/路径
sudo systemctl daemon-reload
sudo systemctl enable --now chat-data

# 3. 查看状态与日志
sudo systemctl status chat-data
journalctl -u chat-data -f
```

特性：开机自启、崩溃 5 秒后自动拉起、2 个 worker 进程。

## 五、方式 C：Docker

```bash
docker build -t chat-data .
docker run -d --name chat-data \
  --env-file .env \
  -p 8000:8000 \
  --restart unless-stopped \
  chat-data
```

## 六、可选：Nginx 反向代理（80 端口直出）

```nginx
server {
    listen 80;
    server_name your.domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

配置后用户无需输端口号，直接 `http://your.domain.com` 访问。

## 七、防火墙放行

- 云服务器安全组 / 防火墙放行 **8000**（或 Nginx 的 **80**）入站
- 应用服务器需能**出站**访问 PostgreSQL 5432 与 LLM API 地址

## 八、常见问题

| 现象 | 排查 |
|------|------|
| 页面打开但「数据库连接失败」 | `.env` 是否正确；应用服务器到 DB 的 5432 端口是否连通（`Test-NetConnection 主机 -Port 5432` / `telnet 主机 5432`）；DB 安全组是否放行应用服务器 IP |
| 提问报「LLM 相关错误」 | `.env` 的 `LLM_API_KEY` / `LLM_BASE_URL`；或在页面配置区填写 |
| 访问 8000 无响应 | 服务是否在跑（`systemctl status` / 进程列表）；防火墙是否放行 |
| 只改了前端代码 | `cd frontend && npm run build` 后刷新即可，无需重启后端 |
