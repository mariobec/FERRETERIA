@echo off
setlocal EnableDelayedExpansion
title LhexIA ERP - Operacion

call "%~dp0_ir_raiz_erp.bat"

if not exist "%ERP_ROOT%.env.local" (
  echo.
  echo [ERROR] Falta %ERP_ROOT%.env.local
  echo.
  echo   El ERP necesita PostgreSQL configurado. Ejecute en este PC:
  echo     00_Instalar_servidor_completo.bat
  echo   ^(al menos pasos 1 PostgreSQL y 4 base de datos^).
  echo.
  echo   Si ya instalo Postgres, copie la clave en erp\.env.local:
  echo     DATABASE_URL=postgresql://postgres:SU_CLAVE@localhost:5432/ferreteria_local
  echo.
  pause
  exit /b 1
)

set "PGCLIENTENCODING=UTF8"
set "ERP_PG_DRIVER=pg8000"
set "FLASK_DEBUG=0"
set "FLASK_TEMPLATE_RELOAD=0"
set "FLASK_RUN_HOST=0.0.0.0"

if /I "%LHEXIA_RUNTIME_MODE%"=="exe" goto :url_exe

set "VENV_PY=%ERP_ROOT%.venv\Scripts\python.exe"
if not exist "%VENV_PY%" set "VENV_PY=%ERP_ROOT%venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
  echo [ERROR] No hay .venv ni LhexIA_ERP.exe
  echo Ejecute COMPILAR_ERP_EXE.bat o 00_Instalar_servidor_completo.bat
  pause
  exit /b 1
)
for /f "delims=" %%U in ('"%VENV_PY%" "%ERP_ROOT%scripts\configurar_url_red_erp.py" --mostrar 2^>nul') do set "URL_FIJA=%%U"
goto :banner

:url_exe
for /f "delims=" %%U in ('"%ERP_ROOT%LhexIA_ERP.exe" url-red --mostrar 2^>nul') do set "URL_FIJA=%%U"

:banner
echo.
echo ============================================
echo   LhexIA ERP - MODO OPERACION
if /I "%LHEXIA_RUNTIME_MODE%"=="exe" (echo   Runtime: ejecutable ^(sin codigo fuente^)) else (echo   Runtime: Python .venv)
echo   Local:  http://127.0.0.1:5000/login
if defined URL_FIJA (
  echo !URL_FIJA! | findstr /I "sin URL fija" >nul
  if errorlevel 1 echo   Tablets: !URL_FIJA!/login
)
if not defined URL_FIJA (
  echo   Tablets ^(IP actual^):
  powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' -and $_.IPAddress -notlike '169.254.*' } | ForEach-Object { Write-Host ('     http://' + $_.IPAddress + ':5000/login') }"
)
echo   Detener: CTRL+C
echo ============================================
echo.

for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":5000 .*LISTENING"') do (
  echo [AVISO] Puerto 5000 en uso por PID %%P — cierre la otra ventana del ERP.
  echo.
)

if /I "%LHEXIA_RUNTIME_MODE%"=="exe" (
  "%ERP_ROOT%LhexIA_ERP.exe"
) else (
  "%VENV_PY%" "%ERP_ROOT%app.py"
)
set "EC=%errorlevel%"
if not "%EC%"=="0" (
  echo [ERROR] Servidor termino con codigo %EC%
  pause
)
exit /b %EC%
