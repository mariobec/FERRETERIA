@echo off
setlocal EnableDelayedExpansion
title LhexIA ERP - Arranque con LOG

call "%~dp0_ir_raiz_erp.bat"
if errorlevel 1 pause & exit /b 1

if not exist "%ERP_ROOT%logs" mkdir "%ERP_ROOT%logs"
set "LOG=%ERP_ROOT%logs\arranque_erp_%DATE:~-4%%DATE:~3,2%%DATE:~0,2%.log"

echo ============================================ > "%LOG%"
echo Arranque ERP %DATE% %TIME% >> "%LOG%"
echo ERP_ROOT=%ERP_ROOT% >> "%LOG%"
echo ============================================ >> "%LOG%"
echo.

echo Carpeta ERP: %ERP_ROOT%
echo Log: %LOG%
echo.

if not exist "%ERP_ROOT%LhexIA_ERP.exe" (
  echo [ERROR] Falta LhexIA_ERP.exe >> "%LOG%"
  echo [ERROR] Falta LhexIA_ERP.exe
  echo Copie la carpeta erp COMPLETA del pendrive ^(_internal incluido^).
  pause
  exit /b 1
)

if not exist "%ERP_ROOT%_internal" (
  echo [ERROR] Falta _internal\ >> "%LOG%"
  echo [ERROR] Falta carpeta _internal\
  echo La copia del USB quedo incompleta. Vuelva a copiar erp\ entera.
  pause
  exit /b 1
)

if not exist "%ERP_ROOT%.env.local" (
  echo [ERROR] Falta .env.local >> "%LOG%"
  echo [ERROR] Falta erp\.env.local
  echo Restaure desde erp_backup_* o copie el .env.local del respaldo.
  pause
  exit /b 1
)

echo [OK] exe + _internal + .env.local >> "%LOG%"
echo [OK] Archivos basicos presentes. Arrancando...
echo.

cd /d "%ERP_ROOT%"
"%ERP_ROOT%LhexIA_ERP.exe" >> "%LOG%" 2>&1
set "EC=%errorlevel%"

echo. >> "%LOG%"
echo Fin codigo %EC% %TIME% >> "%LOG%"
echo.
echo Servidor termino con codigo %EC%
echo Revise el log: %LOG%
echo.
type "%LOG%"
echo.
pause
exit /b %EC%
