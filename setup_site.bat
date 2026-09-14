@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt -c constraints-verified.txt
if errorlevel 1 goto failed
echo SAF setup completed. Run run_site.bat to start the website.
pause
exit /b 0
:failed
echo Setup failed. Please check Python 3.12 and the network connection.
pause
exit /b 1
