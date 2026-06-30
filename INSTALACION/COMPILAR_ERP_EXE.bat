@echo off
setlocal
title LhexIA - Compilar ERP (PyInstaller, sin codigo fuente)

for %%I in ("%~dp0..") do set "REPO=%%~fI"
set "PY=%REPO%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo.
echo ============================================
echo   Compilar LhexIA_ERP.exe (PyInstaller)
echo ============================================
echo Repo: %REPO%
echo.

"%PY%" -c "import PyInstaller" 2>nul
if errorlevel 1 (
  echo [1/3] Instalando PyInstaller...
  "%PY%" -m pip install pyinstaller -q
)

echo [2/3] Compilando (puede tardar varios minutos)...
"%PY%" "%REPO%\scripts\build_pyinstaller_erp.py" --clean
if errorlevel 1 (
  echo [ERROR] Compilacion fallida
  pause
  exit /b 1
)

echo [3/3] Validando build...
"%PY%" "%REPO%\scripts\validar_build_pyinstaller_erp.py"
if errorlevel 1 (
  echo.
  echo [ERROR] Validacion fallida — NO copie al cliente hasta corregir.
  pause
  exit /b 1
)

echo.
echo [OK] Listo: INSTALACION\erp\LhexIA_ERP.exe
echo Copie carpeta INSTALACION completa al PC servidor.
echo.
pause
exit /b 0
