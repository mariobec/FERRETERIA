@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

REM Restaura dump piloto SD en Postgres local (máquina de tienda).
REM Uso: restaurar_piloto_tienda.bat "RUTA\piloto_sd_ferreteria_YYYYMMDD_HHMM.dump"

if "%~1"=="" (
  echo ERROR: Indique la ruta al archivo .dump
  echo Ejemplo: restaurar_piloto_tienda.bat "D:\LhexIA_Piloto\01_BASE_DATOS\piloto_sd_ferreteria_20260529.dump"
  pause
  exit /b 1
)

set "DUMP=%~1"
if not exist "%DUMP%" (
  echo ERROR: No existe el archivo: %DUMP%
  pause
  exit /b 1
)

set "PG_BIN=C:\Program Files\PostgreSQL\18\bin"
if not exist "%PG_BIN%\pg_restore.exe" set "PG_BIN=C:\Program Files\PostgreSQL\17\bin"
if not exist "%PG_BIN%\pg_restore.exe" set "PG_BIN=C:\Program Files\PostgreSQL\16\bin"

set "DB=ferreteria_local"
set "PGHOST=localhost"
set "PGPORT=5432"
set "PGUSER=postgres"

echo.
echo Restaurando en %DB% ...
echo Archivo: %DUMP%
echo.

"%PG_BIN%\pg_restore.exe" -h %PGHOST% -p %PGPORT% -U %PGUSER% -d %DB% --no-owner --no-acl --clean --if-exists "%DUMP%"
if errorlevel 1 (
  echo.
  echo AVISO: pg_restore puede mostrar warnings; revise si la app arranca OK.
)

echo.
echo Listo. Pruebe: arrancar_erp.bat
pause
