@echo off
setlocal EnableDelayedExpansion
title LhexIA - [3/5] Aplicacion ERP

set "PACK=%~dp0"
call "%PACK%instalador.defaults.bat"

echo.
echo === Paso 3/5 - Aplicacion en %LHEXIA_INSTALL_DIR% ===
echo.

if exist "%LHEXIA_INSTALL_DIR%\LhexIA_ERP.exe" (
  echo [OK] Runtime ejecutable ^(PyInstaller^) — sin .venv
  call "%PACK%_escribir_env_local.bat" "%LHEXIA_INSTALL_DIR%\.env.local"
  if exist "%PACK%03_CONFIG\empresa_config.json" (
    if not exist "%LHEXIA_INSTALL_DIR%\data" mkdir "%LHEXIA_INSTALL_DIR%\data"
    copy /Y "%PACK%03_CONFIG\empresa_config.json" "%LHEXIA_INSTALL_DIR%\data\empresa_config.json" >nul
  )
  if exist "%PACK%03_CONFIG\zebra_etiqueta_config.json" (
    if not exist "%LHEXIA_INSTALL_DIR%\data" mkdir "%LHEXIA_INSTALL_DIR%\data"
    if not exist "%LHEXIA_INSTALL_DIR%\data\zebra_etiqueta_config.json" (
      copy /Y "%PACK%03_CONFIG\zebra_etiqueta_config.json" "%LHEXIA_INSTALL_DIR%\data\zebra_etiqueta_config.json" >nul
    )
  )
  echo [OK] Paso 3 listo — NO se crea .venv ^(usa LhexIA_ERP.exe^)
  exit /b 0
)

if not exist "%LHEXIA_INSTALL_DIR%\app.py" (
  echo [ERROR] Falta LhexIA_ERP.exe o app.py en %LHEXIA_INSTALL_DIR%
  echo En DEV: COMPILAR_ERP_EXE.bat ^(recomendado^) o EMPAQUETAR_desde_DEV.bat
  pause
  exit /b 1
)

py -3 -c "import sys; raise SystemExit(0 if sys.version_info[:2]>=(3,11) else 1)" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python 3.11+ requerido. Paso 2 primero.
  exit /b 1
)

cd /d "%LHEXIA_INSTALL_DIR%"

if exist ".venv" rmdir /s /q ".venv"
py -3 -m venv .venv
if errorlevel 1 exit /b 1
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip -q

if exist "%PACK%05_WHEELS\*.whl" (
  pip install --no-index --find-links="%PACK%05_WHEELS" -r requirements.txt -q
) else (
  pip install -r requirements.txt -q
)
pip install pywin32 pg8000 -q

if exist "%PACK%03_CONFIG\.env.local.template" (
  copy /Y "%PACK%03_CONFIG\.env.local.template" ".env.local" >nul
) else if exist "%PACK%03_CONFIG\.env.local" (
  copy /Y "%PACK%03_CONFIG\.env.local" ".env.local" >nul
)

if exist "%PACK%03_CONFIG\empresa_config.json" (
  if not exist "data" mkdir "data"
  copy /Y "%PACK%03_CONFIG\empresa_config.json" "data\empresa_config.json" >nul
)

echo [OK] .venv listo en erp\
exit /b 0
