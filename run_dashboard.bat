@echo off
echo ========================================================
echo   SEMANTIC SENTINEL - TACTICAL COMMAND CENTER (HUD)
echo ========================================================
echo Starting Tactical Command Server at http://localhost:5000 ...
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)
start http://localhost:5000
python web_server.py
pause


