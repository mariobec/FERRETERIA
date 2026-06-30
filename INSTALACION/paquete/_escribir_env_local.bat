@echo off
REM Escribe erp\.env.local con Postgres local (instalador portable).
setlocal EnableDelayedExpansion
set "PACK=%~dp0"
call "%PACK%instalador.defaults.bat"

set "DEST=%~1"
if not defined DEST set "DEST=%LHEXIA_INSTALL_DIR%\.env.local"

if not defined LHEXIA_PG_SUPERPASS (
  if exist "%PACK%.instalacion_pg_pass" set /p LHEXIA_PG_SUPERPASS=<"%PACK%.instalacion_pg_pass"
)

if not defined LHEXIA_PG_SUPERPASS (
  echo [AVISO] Sin clave postgres — use paso 1 del instalador o edite %DEST%
  set "LHEXIA_PG_SUPERPASS=CAMBIAR_CLAVE_POSTGRES"
)

(
  echo DATABASE_URL=postgresql://%LHEXIA_PG_USER%:%LHEXIA_PG_SUPERPASS%@localhost:%LHEXIA_PG_PORT%/%LHEXIA_DB_NAME%
  echo ERP_PG_DRIVER=pg8000
  echo PGCLIENTENCODING=UTF8
  echo FLASK_RUN_HOST=0.0.0.0
  echo FLASK_DEBUG=0
) > "%DEST%"
exit /b 0
