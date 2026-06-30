@echo off
setlocal
title LhexIA ERP - Arranque automatico completo

call "%~dp0_ir_raiz_erp.bat"

net session >nul 2>&1
if errorlevel 1 (
  echo [AVISO] Sin admin — solo tarea ERP.
  goto :erp
)

call "%~dp0configurar_postgres_arranque_automatico.bat"

:erp
call "%~dp0registrar_arranque_automatico.bat"
exit /b 0
