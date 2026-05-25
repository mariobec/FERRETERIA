@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PGCLIENTENCODING=UTF8

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Falta .venv — ejecuta:
    echo   python -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo LhexIA ERP: http://localhost:5000
".venv\Scripts\python.exe" app.py
pause
