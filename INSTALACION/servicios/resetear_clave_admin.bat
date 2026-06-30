@echo off
setlocal
title LhexIA ERP - Resetear clave

call "%~dp0_ir_raiz_erp.bat"

set "CORREO=admin@local.cl"
set /p CORREO=Correo [%CORREO%]: 
if "%CORREO%"=="" set "CORREO=admin@local.cl"

set "NUEVA=AdminSD2026!"
set /p NUEVA=Nueva clave [%NUEVA%]: 
if "%NUEVA%"=="" set "NUEVA=AdminSD2026!"

if /I "%LHEXIA_RUNTIME_MODE%"=="exe" (
  "%ERP_ROOT%LhexIA_ERP.exe" reset-clave --correo "%CORREO%" --clave "%NUEVA%"
) else (
  set "PY=%ERP_ROOT%.venv\Scripts\python.exe"
  if not exist "%PY%" set "PY=python"
  "%PY%" "%ERP_ROOT%scripts\resetear_clave_admin.py" --correo "%CORREO%" --clave "%NUEVA%"
)
pause
