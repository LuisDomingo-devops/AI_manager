@echo off
cd /d "%~dp0"
start "Alfonso Autonomo" "%~dp0venv\Scripts\python.exe" "%~dp0client\cliente.py" --gui
