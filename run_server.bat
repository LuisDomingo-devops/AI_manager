@echo off
cd /d "%~dp0"
title Alfonso Server Core (FastAPI)
echo ========================================================
echo   INICIANDO SERVIDOR CORE ALFONSO (FastAPI en :8000)
echo ========================================================
"%~dp0venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
