@echo off
setlocal ENABLEDELAYEDEXPANSION
title ERP Ferreteria - Inicio DEMO

if not exist ".venv\Scripts\activate.bat" (
  echo [ERROR] No existe entorno virtual. Ejecuta primero instalar_demo_windows.bat
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
  echo [ERROR] No se pudo activar entorno virtual.
  pause
  exit /b 1
)

if exist ".env.demo" (
  for /f "usebackq tokens=1,* delims==" %%A in (".env.demo") do (
    if not "%%A"=="" if /i not "%%A:~0,1%%"=="#" set "%%A=%%B"
  )
) else (
  echo [ERROR] Falta archivo .env.demo (copia env.demo.ejemplo y renombra).
  pause
  exit /b 1
)

echo Iniciando ERP DEMO en http://127.0.0.1:5000
echo (Presiona CTRL+C para detener)
echo.
python app.py
exit /b %errorlevel%
