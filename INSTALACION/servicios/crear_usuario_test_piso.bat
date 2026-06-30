@echo off
setlocal
title LhexIA ERP - Usuario prueba tablet

call "%~dp0_ir_raiz_erp.bat"

set "PGCLIENTENCODING=UTF8"

if /I "%LHEXIA_RUNTIME_MODE%"=="exe" (
  "%ERP_ROOT%LhexIA_ERP.exe" crear-usuario-test %*
  set "EC=%errorlevel%"
  pause
  exit /b %EC%
)

set "PY=%ERP_ROOT%.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo [ERROR] Falta .venv — use LhexIA_ERP.exe o reinstale con COMPILAR_ERP_EXE.bat
  pause
  exit /b 1
)
"%PY%" "%ERP_ROOT%scripts\crear_usuario_test_piso.py" %*
pause
exit /b %errorlevel%
