@echo off
setlocal
title LhexIA ERP - Tarea arranque ERP

call "%~dp0_ir_raiz_erp.bat"

set "SCRIPT=%ERP_ROOT%servidor_erp_autostart.ps1"
if not exist "%SCRIPT%" set "SCRIPT=%ERP_ROOT%scripts\servidor_erp_autostart.ps1"
if not exist "%SCRIPT%" (
  echo [ERROR] Falta %SCRIPT%
  pause
  exit /b 1
)

schtasks /Create /F /TN "LhexIA ERP Servidor" /SC ONLOGON /DELAY 0000:45 /RL LIMITED /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"%SCRIPT%\""

if errorlevel 1 (
  echo [ERROR] No se pudo registrar. Pruebe como administrador.
  pause
  exit /b 1
)
echo [OK] Tarea creada. Probar: schtasks /Run /TN "LhexIA ERP Servidor"
pause
exit /b 0
