@echo off
title ERP - Generar carpeta DEMO_FERRETERIA_ERP
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0empaquetar_demo_cliente.ps1"
if errorlevel 1 (
  echo.
  echo [ERROR] Fallo el empaquetado. Revisa mensajes arriba.
  pause
  exit /b 1
)
echo.
pause
