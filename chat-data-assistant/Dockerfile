# ── 阶段 1：构建前端 ──
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ── 阶段 2：Python 运行时 ──
FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/
COPY ai/ ./ai/
COPY core/ ./core/
COPY db/ ./db/
COPY schema/ ./schema/
COPY config.py ./
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# .env 通过 docker run --env-file 或 compose 注入，不打入镜像
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
