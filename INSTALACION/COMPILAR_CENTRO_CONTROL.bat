@echo off
setlocal
title LhexIA - Compilar Centro de Control (.exe)

for %%I in ("%~dp0..") do set "REPO=%%~fI"
set "PY=%REPO%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo.
echo ============================================
echo   Compilar LhexIA_Centro_Control.exe
echo ============================================
echo.

"%PY%" -m pip install pyinstaller -q
if errorlevel 1 (
  echo [ERROR] pip install pyinstaller fallo
  pause
  exit /b 1
)

set "SCRIPT=%REPO%\scripts\lhexia_centro_control.py"
set "DIST=%REPO%\dist"
set "WORK=%REPO%\build\pyinstaller_centro_control"
set "ICON=%REPO%\respaldos\LhexIA_Instalador_SD\02_APLICACION\instalador_intranet\inno\assets\setup_icon.ico"
if not exist "%ICON%" set "ICON="

if defined ICON (
  "%PY%" -m PyInstaller --onefile --windowed --name LhexIA_Centro_Control --distpath "%DIST%" --workpath "%WORK%" --specpath "%WORK%" --clean --icon "%ICON%" "%SCRIPT%"
) else (
  "%PY%" -m PyInstaller --onefile --windowed --name LhexIA_Centro_Control --distpath "%DIST%" --workpath "%WORK%" --specpath "%WORK%" --clean "%SCRIPT%"
)
if errorlevel 1 (
  echo [ERROR] PyInstaller fallo
  pause
  exit /b 1
)

copy /Y "%DIST%\LhexIA_Centro_Control.exe" "%~dp0LhexIA_Centro_Control.exe" >nul
echo [OK] %~dp0LhexIA_Centro_Control.exe
echo Copie INSTALACION completa al USB.
pause
exit /b 0
