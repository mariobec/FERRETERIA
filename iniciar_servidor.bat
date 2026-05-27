@echo off
setlocal ENABLEDELAYEDEXPANSION
title LhexIA ERP - Servidor local
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo.
  echo [ERROR] No se encuentra el entorno virtual en .venv
  echo.
  echo   En Windows NO use:  python app.py
  echo   Eso usa Python del sistema y falla con "No module named flask".
  echo.
  echo   Primero instale dependencias:
  echo     instalar_pruebas_windows.bat
  echo.
  echo   Luego inicie con este archivo o:
  echo     .venv\Scripts\python.exe app.py
  echo.
  pause
  exit /b 1
)

set "PGCLIENTENCODING=UTF8"
set "FLASK_DEBUG=1"

echo.
echo ============================================
echo   LhexIA ERP - http://127.0.0.1:5000
echo   Python: %PY%
echo   Detener: CTRL+C
echo ============================================
echo.

"%PY%" -c "import flask" 2>nul
if errorlevel 1 (
  echo [ERROR] Flask no esta instalado en .venv
  echo Ejecute: instalar_pruebas_windows.bat
  pause
  exit /b 1
)

for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":5000 .*LISTENING"') do (
  echo [AVISO] Puerto 5000 en uso por PID %%P
  echo Cierre la otra ventana del ERP o mate el proceso desde el Administrador de tareas.
  echo.
)

"%PY%" app.py
set "EC=%errorlevel%"
if not "%EC%"=="0" (
  echo.
  echo [ERROR] El servidor termino con codigo %EC%
  pause
)
exit /b %EC%
