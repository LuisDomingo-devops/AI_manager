@echo off
cd /d "%~dp0"
echo ========================================================
echo   INICIANDO ALFONSO AUTONOMO (SERVIDOR + INTERFAZ GUI)
echo ========================================================
start "Alfonso Server" "%~dp0venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
timeout /t 3 /nobreak >nul
start "Alfonso HUD Dashboard" "%~dp0venv\Scripts\python.exe" "%~dp0client\cliente.py" --gui
