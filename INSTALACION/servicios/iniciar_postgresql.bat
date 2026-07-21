@echo off
setlocal
title LhexIA - Iniciar PostgreSQL
set "SILENT=%~1"

echo.
echo ============================================
echo   Iniciar PostgreSQL
echo ============================================
echo.

set "PG_FOUND=0"
for /f "tokens=1" %%S in ('powershell -NoProfile -Command "Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name"') do (
  set "PG_FOUND=1"
  sc query "%%S" | findstr /I RUNNING >nul
  if errorlevel 1 (
    echo Iniciando %%S ...
    net start "%%S"
  ) else (
    echo [OK] %%S ya esta en ejecucion
  )
)

if "%PG_FOUND%"=="0" (
  echo [ERROR] No se encontro servicio postgresql*
  echo Ejecute 00_Instalar_servidor_completo.bat o paquete\01_instalar_postgresql.bat
)

echo.
netstat -ano | findstr /R /C:":5432 .*LISTENING" >nul && echo Puerto 5432: [OK] || echo Puerto 5432: [FAIL]
echo.
if /I not "%SILENT%"=="silent" pause
exit /b 0
