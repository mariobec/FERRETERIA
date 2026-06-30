@echo off
setlocal EnableDelayedExpansion
title LhexIA - [4/5] Base de datos

set "PACK=%~dp0"
call "%PACK%instalador.defaults.bat"

echo.
echo === Paso 4/5 - Restaurar base de datos ===
echo.

set "PG_BIN=C:\Program Files\PostgreSQL\18\bin"
if not exist "%PG_BIN%\psql.exe" set "PG_BIN=C:\Program Files\PostgreSQL\17\bin"
if not exist "%PG_BIN%\psql.exe" set "PG_BIN=C:\Program Files\PostgreSQL\16\bin"
if not exist "%PG_BIN%\psql.exe" (
  echo [ERROR] psql no encontrado. Paso 1 primero.
  exit /b 1
)

set "DUMP="
for %%F in ("%PACK%01_BASE_DATOS\lhexia_sd_*.dump") do set "DUMP=%%~fF"
if not defined DUMP for %%F in ("%PACK%01_BASE_DATOS\*.dump") do set "DUMP=%%~fF"

if not defined DUMP (
  echo [ERROR] Coloque un .dump en %PACK%01_BASE_DATOS\
  pause
  exit /b 1
)

if not defined LHEXIA_PG_SUPERPASS (
  if exist "%PACK%.instalacion_pg_pass" set /p LHEXIA_PG_SUPERPASS=<"%PACK%.instalacion_pg_pass"
)
if not defined LHEXIA_PG_SUPERPASS (
  set /p LHEXIA_PG_SUPERPASS=Clave postgres (paso 1): 
)

set "PGPASSWORD=%LHEXIA_PG_SUPERPASS%"

"%PG_BIN%\psql.exe" -h localhost -p %LHEXIA_PG_PORT% -U %LHEXIA_PG_USER% -d postgres -tc "SELECT 1 FROM pg_database WHERE datname = '%LHEXIA_DB_NAME%'" | findstr /I "1" >nul
if errorlevel 1 (
  "%PG_BIN%\createdb.exe" -h localhost -p %LHEXIA_PG_PORT% -U %LHEXIA_PG_USER% %LHEXIA_DB_NAME%
)

echo Restaurando %DUMP% ...
"%PG_BIN%\pg_restore.exe" -h localhost -p %LHEXIA_PG_PORT% -U %LHEXIA_PG_USER% -d %LHEXIA_DB_NAME% --no-owner --no-acl --clean --if-exists "%DUMP%"
if errorlevel 1 (
  echo [AVISO] pg_restore mostro advertencias — si el login ERP funciona, puede continuar.
)

call "%PACK%_escribir_env_local.bat" "%LHEXIA_INSTALL_DIR%\.env.local"

if exist "%LHEXIA_INSTALL_DIR%\LhexIA_ERP.exe" (
  echo [OK] Modo ejecutable — no se crea .venv ^(normal^).
)

echo [OK] Base %LHEXIA_DB_NAME% y .env.local configurados.
exit /b 0
