@echo off
setlocal ENABLEDELAYEDEXPANSION
title ERP Ferreteria - Inicio pruebas QA
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
  echo [ERROR] No existe entorno virtual. Ejecuta primero instalar_pruebas_windows.bat
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
  echo [ERROR] No se pudo activar entorno virtual.
  pause
  exit /b 1
)

if exist "env_qa.txt" (
  for /f "usebackq tokens=1,* delims==" %%A in ("env_qa.txt") do (
    if not "%%A"=="" if /i not "%%A:~0,1%%"=="#" set "%%A=%%B"
  )
)
if exist ".env.qa" (
  for /f "usebackq tokens=1,* delims==" %%A in (".env.qa") do (
    if not "%%A"=="" if /i not "%%A:~0,1%%"=="#" set "%%A=%%B"
  )
)

echo Iniciando ERP en http://127.0.0.1:5000
echo (Presiona CTRL+C para detener)
echo.
python app.py
exit /b %errorlevel%
