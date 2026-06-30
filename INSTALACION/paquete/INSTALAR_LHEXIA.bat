@echo off
setlocal
title LhexIA ERP - Instalador (carpeta INSTALACION)

cd /d "%~dp0"
if /I "%~1"=="silent" set "LHEXIA_SILENT=1"

echo.
echo ############################################################
echo   LhexIA ERP - Instalacion servidor (todo en esta carpeta)
echo ############################################################
echo.
echo   Carpeta: %~dp0..
echo   Aplicacion: erp\
echo.
echo Pasos: PostgreSQL - Aplicacion - Base de datos - Accesos
if exist "%LHEXIA_INSTALL_DIR%\LhexIA_ERP.exe" (
  echo   Modo: LhexIA_ERP.exe ^(NO requiere Python ni .venv^)
) else (
  echo   Modo: Python + .venv ^(legacy^)
)
echo.

call "%~dp0instalador.defaults.bat"
set "LHEXIA_EXE_MODE=0"
if exist "%LHEXIA_INSTALL_DIR%\LhexIA_ERP.exe" set "LHEXIA_EXE_MODE=1"
if not exist "%LHEXIA_INSTALL_DIR%\LhexIA_ERP.exe" (
  if not exist "%LHEXIA_INSTALL_DIR%\app.py" (
    echo [ERROR] Falta LhexIA_ERP.exe o app.py en %LHEXIA_INSTALL_DIR%
    echo.
    echo   En DEV ejecute: INSTALACION\COMPILAR_ERP_EXE.bat
    echo   Copie al USB la carpeta INSTALACION COMPLETA ^(incluye erp\^).
    echo   NO use paquetes viejos LhexIA_Instalador_SD / 02_APLICACION.
    echo.
    if not defined LHEXIA_SILENT pause
    exit /b 1
  )
)

if not defined LHEXIA_SILENT pause

call "%~dp001_instalar_postgresql.bat"
if errorlevel 1 goto :error

if "%LHEXIA_EXE_MODE%"=="1" (
  echo.
  echo [OK] Paso 2/5 Python — omitido ^(modo LhexIA_ERP.exe^)
  echo.
) else (
  call "%~dp002_instalar_python.bat"
  if errorlevel 1 goto :error
)

call "%~dp003_instalar_aplicacion.bat"
if errorlevel 1 goto :error

call "%~dp004_instalar_base_datos.bat"
if errorlevel 1 goto :error

call "%~dp005_configurar_intranet.bat"

echo.
echo ============================================
echo   INSTALACION COMPLETA
echo ============================================
echo.
echo Abra: ..\01_Centro_de_Control.bat  o  ..\02_Iniciar_ERP.bat
echo Login: http://127.0.0.1:5000/login
echo.
if not defined LHEXIA_SILENT pause
exit /b 0

:error
echo.
echo [ERROR] Instalacion interrumpida.
if not defined LHEXIA_SILENT pause
exit /b 1
