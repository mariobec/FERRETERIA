@echo off
setlocal EnableDelayedExpansion
title LhexIA - [2/5] Python

set "PACK=%~dp0"
call "%PACK%instalador.defaults.bat"

echo.
echo === Paso 2/5 - Python 3.12+ ===
echo.

py -3 -c "import sys; raise SystemExit(0 if sys.version_info[:2]>=(3,11) else 1)" >nul 2>&1
if not errorlevel 1 (
  for /f "delims=" %%V in ('py -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"') do echo [OK] Python %%V
  exit /b 0
)

set "PY_EXE="
for %%F in ("%PACK%00_PYTHON\python-*-amd64.exe") do set "PY_EXE=%%~fF"
if not defined PY_EXE for %%F in ("%PACK%00_PYTHON\python*.exe") do set "PY_EXE=%%~fF"

if not defined PY_EXE (
  echo [ERROR] Coloque python-3.12*-amd64.exe en %PACK%00_PYTHON\
  pause
  exit /b 1
)

"%PY_EXE%" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0 Include_pip=1 Include_launcher=1
if errorlevel 1 exit /b 1
py -3 -c "import sys; print('Python', sys.version)" 2>nul || (
  echo Cierre y vuelva a ejecutar INSTALAR_LHEXIA.bat
  exit /b 1
)
exit /b 0
