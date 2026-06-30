@echo off
setlocal EnableDelayedExpansion
title LhexIA - [1/5] PostgreSQL

set "PACK=%~dp0"
call "%PACK%instalador.defaults.bat"

echo.
echo === Paso 1/5 - PostgreSQL ===
echo.

set "PG_FOUND=0"
for /f "tokens=1" %%S in ('powershell -NoProfile -Command "Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name"') do (
  set "PG_FOUND=1"
  echo [OK] Ya instalado: %%S
)

if "!PG_FOUND!"=="1" goto :ensure_running

set "PG_EXE="
for %%F in ("%PACK%00_POSTGRESQL\postgresql-*-windows-x64.exe") do set "PG_EXE=%%~fF"
if not defined PG_EXE for %%F in ("%PACK%00_POSTGRESQL\*.exe") do set "PG_EXE=%%~fF"

if not defined PG_EXE (
  echo [ERROR] Coloque postgresql-*-windows-x64.exe en:
  echo   %PACK%00_POSTGRESQL\
  pause
  exit /b 1
)

if not defined LHEXIA_PG_SUPERPASS (
  set /p LHEXIA_PG_SUPERPASS=Clave postgres (anotela): 
)
echo %LHEXIA_PG_SUPERPASS%> "%PACK%.instalacion_pg_pass"

set "PG_SERVICE=postgresql-x64-18"
echo !PG_EXE! | findstr /I "postgresql-16" >nul && set "PG_SERVICE=postgresql-x64-16"
echo !PG_EXE! | findstr /I "postgresql-17" >nul && set "PG_SERVICE=postgresql-x64-17"

echo Instalando PostgreSQL silencioso...
"%PG_EXE%" --mode unattended --unattendedmodeui none --superpassword "%LHEXIA_PG_SUPERPASS%" --servicename "!PG_SERVICE!" --servicepassword "%LHEXIA_PG_SUPERPASS%" --serverport %LHEXIA_PG_PORT% --install_runtimes 1
if errorlevel 1 exit /b 1

:ensure_running
for /f "tokens=1" %%S in ('powershell -NoProfile -Command "Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name"') do (
  sc config "%%S" start= auto >nul 2>&1
  sc query "%%S" | findstr /I RUNNING >nul || net start "%%S" >nul 2>&1
)
exit /b 0
