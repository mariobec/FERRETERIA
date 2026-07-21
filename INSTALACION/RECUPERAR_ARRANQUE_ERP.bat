@echo off
setlocal EnableDelayedExpansion
title LhexIA - Recuperar arranque ERP

call "%~dp0servicios\_ir_raiz_erp.bat"
if errorlevel 1 pause & exit /b 1

echo.
echo ============================================
echo   Recuperacion arranque LhexIA ERP
echo   Carpeta erp: %ERP_ROOT%
echo ============================================
echo.

set "OK=1"

echo [1/6] LhexIA_ERP.exe
if exist "%ERP_ROOT%LhexIA_ERP.exe" (echo   [OK]) else (echo   [FAIL] Falta exe & set "OK=0")

echo [2/6] _internal\
if exist "%ERP_ROOT%_internal" (echo   [OK]) else (echo   [FAIL] Falta _internal — copie erp\ COMPLETA del USB & set "OK=0")

echo [3/6] .env.local ^(PostgreSQL^)
if exist "%ERP_ROOT%.env.local" (
  echo   [OK] Existe
  findstr /I "DATABASE_URL" "%ERP_ROOT%.env.local" >nul || (echo   [FAIL] Sin DATABASE_URL en .env.local & set "OK=0")
) else (
  echo   [FAIL] Falta %ERP_ROOT%.env.local
  echo.
  echo   Busque respaldo erp_backup_* y copie .env.local de ahi.
  echo   O cree el archivo con:
  echo     DATABASE_URL=postgresql://postgres:SU_CLAVE@localhost:5432/ferreteria_local
  echo     ERP_PG_DRIVER=pg8000
  echo     PGCLIENTENCODING=UTF8
  echo     FLASK_RUN_HOST=0.0.0.0
  echo     FLASK_DEBUG=0
  set "OK=0"
)

echo [4/6] PostgreSQL servicio
set "PG=0"
for /f "tokens=1" %%S in ('powershell -NoProfile -Command "Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name"') do (
  set "PG=1"
  echo   [OK] %%S
)
if "!PG!"=="0" echo   [FAIL] Sin servicio postgresql* — ejecute 00_Instalar_servidor_completo.bat paso 1

echo [5/6] Puerto 5432
netstat -ano | findstr /R /C:":5432 .*LISTENING" >nul && echo   [OK] || echo   [FAIL] Postgres no escucha en 5432

echo [6/6] Puerto 5000 libre
netstat -ano | findstr /R /C:":5000 .*LISTENING" >nul && (
  echo   [WARN] Puerto 5000 ocupado — cierre otra instancia del ERP
  for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":5000 .*LISTENING"') do echo        PID %%P
) || echo   [OK]

echo.
if "!OK!"=="0" (
  echo Hay fallos arriba. Corrija y vuelva a ejecutar este script.
  echo.
  pause
  exit /b 1
)

echo Prueba de arranque 15 segundos...
start "LhexIA test" /MIN cmd /c "cd /d %ERP_ROOT% && LhexIA_ERP.exe"
timeout /t 12 /nobreak >nul
powershell -NoProfile -Command "try { $r=Invoke-WebRequest -Uri 'http://127.0.0.1:5000/login' -UseBasicParsing -TimeoutSec 8; Write-Host '[OK] HTTP' $r.StatusCode } catch { Write-Host '[FAIL]' $_.Exception.Message; exit 1 }"
set "HTTP=%errorlevel%"
taskkill /F /IM LhexIA_ERP.exe >nul 2>&1

echo.
if "%HTTP%"=="0" (
  echo [OK] El ERP puede arrancar. Use 02_Iniciar_ERP.bat o Centro de Control.
) else (
  echo [FAIL] El exe no respondio. Ejecute manualmente:
  echo   cd /d %ERP_ROOT%
  echo   LhexIA_ERP.exe
  echo y copie el mensaje de error que aparezca.
)
echo.
pause
exit /b %HTTP%
