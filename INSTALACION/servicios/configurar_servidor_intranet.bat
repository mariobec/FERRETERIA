@echo off
setlocal EnableDelayedExpansion
title LhexIA ERP - Configurar intranet

call "%~dp0_ir_raiz_erp.bat"

echo.
echo ########################################################
echo   Configurar servidor INTRANET (tablets)
echo ########################################################
echo.
pause

net session >nul 2>&1
if errorlevel 1 (
  echo [AVISO] No es administrador — firewall puede fallar.
  pause
)

echo === Firewall puerto 5000 ===
call "%~dp0permitir_erp_red_local.bat"

echo.
echo === URL para tablets ===
call "%~dp0url_erp_red_local.bat"

echo.
echo === Verificacion ===
call "%~dp0verificar_arranque_erp.bat"
exit /b 0
