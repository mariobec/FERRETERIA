@echo off
setlocal
title LhexIA ERP - Arranque automatico Postgres

call "%~dp0_ir_raiz_erp.bat"

net session >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Ejecutar como administrador
  pause
  exit /b 1
)

for /f "tokens=1" %%S in ('powershell -NoProfile -Command "Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name"') do (
  sc config "%%S" start= auto >nul
  sc query "%%S" | findstr /I RUNNING >nul || net start "%%S" >nul 2>&1
  echo [OK] %%S Automatic
)
pause
exit /b 0
