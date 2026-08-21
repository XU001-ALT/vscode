@echo off
rem Chat Data 一键启动（Windows）
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".env" (
    echo [错误] 未找到 .env 文件，请复制 .env.example 为 .env 并填写配置。
    pause
    exit /b 1
)

if not exist "frontend\dist" (
    echo [提示] 未找到 frontend\dist，正在构建前端...
    pushd frontend
    call npm install
    call npm run build
    popd
)

set PY=python
if exist "venv\Scripts\python.exe" set PY=venv\Scripts\python.exe
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe

echo 启动 Chat Data: http://127.0.0.1:8000
"%PY%" -m uvicorn api.main:app --host 0.0.0.0 --port 8000
