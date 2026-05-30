@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

REM Instalacion piloto SD en C:\LhexIA\ (maquina tienda)
REM Estructura esperada:
REM   C:\LhexIA\ERP\              <- este repo (app.py, arrancar_erp.bat)
REM   C:\LhexIA\_piloto\piloto_tienda_pack\  <- copiado del USB
REM   C:\LhexIA\respaldos\        <- backups diarios (opcional)

set "ROOT=C:\LhexIA\ERP"
set "PACK=C:\LhexIA\_piloto\piloto_tienda_pack"
set "PG_BIN=C:\Program Files\PostgreSQL\18\bin"
if not exist "%PG_BIN%\pg_restore.exe" set "PG_BIN=C:\Program Files\PostgreSQL\17\bin"
if not exist "%PG_BIN%\pg_restore.exe" set "PG_BIN=C:\Program Files\PostgreSQL\16\bin"

echo.
echo === LhexIA piloto tienda (instalacion en C:) ===
echo.

if /I not "%CD%"=="%ROOT%" (
  echo AVISO: Ejecute desde %ROOT%
  echo   cd /d "%ROOT%"
  echo   scripts\instalar_piloto_tienda.bat
  echo.
)

if not exist "%ROOT%\app.py" (
  echo ERROR: No esta el proyecto en %ROOT%
  echo Copie la carpeta sistema_ventas_limpio completa a C:\LhexIA\ERP
  pause
  exit /b 1
)

if not exist "%PACK%\01_BASE_DATOS" (
  echo ERROR: Falta el pack del USB en:
  echo   %PACK%
  echo Copie piloto_tienda_pack del pendrive a C:\LhexIA\_piloto\
  pause
  exit /b 1
)

cd /d "%ROOT%"

echo [1/4] Entorno Python (.venv)...
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 (
    echo ERROR: python no encontrado. Instale Python 3.12+
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt -q
if errorlevel 1 (
  echo ERROR: pip install fallo
  pause
  exit /b 1
)
echo OK

echo.
echo [2/4] Restaurar base ferreteria_local...
set "DUMP="
for %%F in ("%PACK%\01_BASE_DATOS\piloto_sd_ferreteria_*.dump") do set "DUMP=%%F"
if not defined DUMP (
  for %%F in ("%PACK%\01_BASE_DATOS\*.dump") do set "DUMP=%%F"
)
if not defined DUMP (
  echo ERROR: No hay archivo .dump en %PACK%\01_BASE_DATOS
  pause
  exit /b 1
)
echo Archivo: !DUMP!
set PGPASSWORD=
"%PG_BIN%\pg_restore.exe" -h localhost -p 5432 -U postgres -d ferreteria_local --no-owner --no-acl --clean --if-exists "!DUMP!"
echo AVISO: warnings de pg_restore son normales si la BD no existia antes.

echo.
echo [3/4] Config .env.local...
if exist "%PACK%\02_CONFIG\.env.local" (
  copy /Y "%PACK%\02_CONFIG\.env.local" "%ROOT%\.env.local" >nul
  echo Copiado .env.local — revise DATABASE_URL=localhost y clave postgres
) else (
  echo AVISO: Falta .env.local en el pack
)

echo.
echo [4/4] Git piloto (opcional)...
where git >nul 2>&1
if not errorlevel 1 (
  git fetch origin 2>nul
  git checkout checkpoint/piloto-sd-local-2026-05-29 2>nul
  if errorlevel 1 git pull origin main 2>nul
)

echo.
echo === Listo ===
echo Carpeta ERP:  %ROOT%
echo Pack piloto:  %PACK%
echo Arrancar:     %ROOT%\arrancar_erp.bat
echo URL local:    http://localhost:5000
echo URL red LAN:  http://IP-DE-ESTA-PC:5000
echo.
echo Ollama (si corre en esta PC): http://127.0.0.1:11434
echo.
pause
