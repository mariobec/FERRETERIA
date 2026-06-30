@echo off
REM Instalacion portable: todo vive dentro de la carpeta INSTALACION
set "PACK=%~dp0"
for %%I in ("%PACK%..") do set "INSTALACION_ROOT=%%~fI\"
set "LHEXIA_INSTALL_DIR=%INSTALACION_ROOT%erp"
set "LHEXIA_DB_NAME=ferreteria_local"
set "LHEXIA_PG_PORT=5432"
set "LHEXIA_PG_USER=postgres"
set "LHEXIA_PG_SUPERPASS="
