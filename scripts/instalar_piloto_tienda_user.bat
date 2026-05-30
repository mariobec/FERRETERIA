@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

REM Piloto SD en carpeta del usuario (sin admin en C:\LhexIA)
REM Proyecto: %USERPROFILE%\Documents\LhexIA\ERP
REM Pack USB: %USERPROFILE%\Documents\LhexIA\_piloto\piloto_tienda_pack

set "ROOT=%USERPROFILE%\Documents\LhexIA\ERP"
set "PACK=%USERPROFILE%\Documents\LhexIA\_piloto\piloto_tienda_pack"
set "PG_BIN=C:\Program Files\PostgreSQL\18\bin"
if not exist "%PG_BIN%\pg_restore.exe" set "PG_BIN=C:\Program Files\PostgreSQL\17\bin"
if not exist "%PG_BIN%\pg_restore.exe" set "PG_BIN=C:\Program Files\PostgreSQL\16\bin"

echo.
echo === LhexIA piloto (Documents\LhexIA) ===
echo Usuario: %USERPROFILE%
echo.

if not exist "%ROOT%\app.py" (
  echo ERROR: Copie el ERP aqui:
  echo   %ROOT%
  echo Debe existir: %ROOT%\app.py
  pause
  exit /b 1
)

if not exist "%PACK%\01_BASE_DATOS" (
  echo ERROR: Copie piloto_tienda_pack del USB aqui:
  echo   %PACK%
  pause
  exit /b 1
)

cd /d "%ROOT%"

echo [1/4] Python .venv ...
if not exist ".venv\Scripts\python.exe" (
  py -m venv .venv 2>nul
  if errorlevel 1 python -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Instale Python 3.12 y marque "Add to PATH"
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt -q

echo [2/4] Restaurar BD ...
set "DUMP="
for %%F in ("%PACK%\01_BASE_DATOS\piloto_sd_ferreteria_*.dump") do set "DUMP=%%F"
if not defined DUMP for %%F in ("%PACK%\01_BASE_DATOS\*.dump") do set "DUMP=%%F"
echo !DUMP!
"%PG_BIN%\pg_restore.exe" -h localhost -p 5432 -U postgres -d ferreteria_local --no-owner --no-acl --clean --if-exists "!DUMP!"

echo [3/4] .env.local ...
if exist "%PACK%\02_CONFIG\.env.local" copy /Y "%PACK%\02_CONFIG\.env.local" "%ROOT%\.env.local" >nul

echo [4/4] Listo.
echo Arrancar: %ROOT%\arrancar_erp.bat
echo URL: http://localhost:5000
pause
