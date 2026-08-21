@echo off
cd /d D:\vscode\chat-data-assistant
call venv\Scripts\activate.bat
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
