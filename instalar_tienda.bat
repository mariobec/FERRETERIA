@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

REM Instalador tienda desde git (QAS / piloto SD)
REM Uso: instalar_tienda.bat
REM Requiere: repo clonado + git + Python + Postgres local

set "REPO=%~dp0"
if "%REPO:~-1%"=="\" set "REPO=%REPO:~0,-1%"
set "PACK=%REPO%\release\instalador_tienda"

echo === LhexIA instalador tienda (desde git) ===
echo Repo: %REPO%
echo Pack: %PACK%
echo.

if not exist "%REPO%\app.py" (
  echo ERROR: Ejecute este .bat desde la raiz del repo clonado.
  pause & exit /b 1
)

if not exist "%PACK%\03_INSTRUCCIONES\instalar_tienda_completo.bat" (
  echo ERROR: Falta release\instalador_tienda en el repo.
  echo Ejecute: git pull origin main
  pause & exit /b 1
)

cd /d "%REPO%"
echo [0/6] git pull origin main ...
git pull origin main
if errorlevel 1 (
  echo AVISO: git pull fallo — continuando con copia local del pack
)

set "LHEXIA_REPO=%REPO%"
call "%PACK%\03_INSTRUCCIONES\instalar_tienda_completo.bat"
