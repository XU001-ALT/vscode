@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Please run setup_site.bat first.
    pause
    exit /b 1
)
echo SAF original website: http://127.0.0.1:8502/
".venv\Scripts\python.exe" -m streamlit run app27.py --server.address=127.0.0.1 --server.port=8502 --browser.gatherUsageStats=false
if errorlevel 1 pause
