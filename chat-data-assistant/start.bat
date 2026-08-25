@echo off
rem Chat Data 一键启动（Windows，前后端分离模式）
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".env" (
    echo [错误] 未找到 .env 文件，请复制 .env.example 为 .env 并填写配置。
    pause
    exit /b 1
)

set PY=python
if exist "venv\Scripts\python.exe" set PY=venv\Scripts\python.exe
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe

echo ========================================
echo   Chat Data 前后端分离启动
echo ========================================
echo.

rem 启动后端 API（端口 8000）
echo [1/2] 启动后端 API: http://127.0.0.1:8000
start "Chat Data API" cmd /c "cd /d "%~dp0" && "%PY%" -m uvicorn api.main:app --host 0.0.0.0 --port 8000"

rem 启动前端开发服务器（端口 5173，自动代理 /api 到后端）
echo [2/2] 启动前端: http://127.0.0.1:5173
pushd frontend
if not exist "node_modules" (
    echo 正在安装前端依赖...
    call npm install
)
start "Chat Data Frontend" cmd /c "cd /d "%~dp0\frontend" && npm run dev"
popd

echo.
echo ========================================
echo   启动完成！
echo   前端界面: http://127.0.0.1:5173
echo   后端 API: http://127.0.0.1:8000
echo ========================================
echo.
pause
