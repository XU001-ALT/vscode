@echo off
rem Chat Data 仅启动后端 API（前后端分离模式）
cd /d D:\vscode\chat-data-assistant
call venv\Scripts\activate.bat
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
