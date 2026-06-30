@echo off
setlocal EnableDelayedExpansion
title LhexIA - Empaquetar INSTALACION para USB

for %%I in ("%~dp0..") do set "REPO=%%~fI"
set "INST=%~dp0"
set "ERP=%INST%erp"
set "OPS=%INST%paquete\04_SCRIPTS_OPERACION"

echo.
echo ============================================
echo   Empaquetar INSTALACION (solo runtime)
echo ============================================
echo Origen codigo: %REPO%
echo Destino erp:   %ERP%
echo.
echo NO incluye: tests, docs, scripts dev, respaldos, git, .venv
echo.

if not exist "%REPO%\app.py" (
  echo [ERROR] Ejecute desde el repo con app.py
  pause
  exit /b 1
)

echo [1/5] Limpiando erp\ ...
if exist "%ERP%" rd /s /q "%ERP%"
mkdir "%ERP%"

echo [2/5] Modulos aplicacion ...
set "MODS=blueprints services core config templates static domain application infrastructure adapters"
for %%D in (%MODS%) do (
  if exist "%REPO%\%%D" (
    echo   + %%D
    robocopy "%REPO%\%%D" "%ERP%\%%D" /E /XD __pycache__ .pytest_cache tests /XF *.pyc *.md /NFL /NDL /NJH /NJS
  )
)

echo [3/5] Archivos raiz ...
for %%F in (app.py requirements.txt schema_sync.py init_db.py) do (
  if exist "%REPO%\%%F" (
    echo   + %%F
    copy /Y "%REPO%\%%F" "%ERP%\" >nul
  )
)

echo [4/5] Scripts operacion (intranet) ...
mkdir "%ERP%\scripts" 2>nul
if exist "%OPS%" (
  copy /Y "%OPS%\*.*" "%ERP%\scripts\" >nul
) else (
  echo [AVISO] Falta paquete\04_SCRIPTS_OPERACION\
)

echo [5/5] Data operativa ...
mkdir "%ERP%\data" 2>nul
for %%F in (empresa_config.json proveedores_config.json cross_sell_associations.json pintura_cartilla_sd.json zebra_etiqueta_config.json) do (
  if exist "%REPO%\data\%%F" copy /Y "%REPO%\data\%%F" "%ERP%\data\" >nul
)
mkdir "%ERP%\storage\dtes\emitidos" 2>nul
mkdir "%ERP%\logs" 2>nul

if not exist "%ERP%\app.py" (
  echo [ERROR] Empaquetado incompleto — falta app.py en erp\
  pause
  exit /b 1
)

if exist "%ERP%\tests" rd /s /q "%ERP%\tests"
if exist "%ERP%\docs" rd /s /q "%ERP%\docs"
if exist "%ERP%\scripts\tareas" rd /s /q "%ERP%\scripts\tareas"

echo.
echo [OK] erp\ listo — solo runtime operativo
for /f %%A in ('dir /s /b "%ERP%\*.py" 2^>nul ^| find /c /v ""') do echo   Archivos .py: %%A
if exist "%ERP%\tests" (echo [AVISO] Quedo carpeta tests — revise) else (echo   tests: no)
if exist "%ERP%\docs" (echo [AVISO] Quedo carpeta docs — revise) else (echo   docs: no)

echo.
echo [CFG] Plantillas instalacion...
if not exist "%INST%paquete\03_CONFIG" mkdir "%INST%paquete\03_CONFIG"
if exist "%REPO%\.env.example" copy /Y "%REPO%\.env.example" "%INST%paquete\03_CONFIG\.env.local.template" >nul
if exist "%REPO%\data\empresa_config.json" copy /Y "%REPO%\data\empresa_config.json" "%INST%paquete\03_CONFIG\empresa_config.json" >nul
if exist "%REPO%\data\zebra_etiqueta_config.json" copy /Y "%REPO%\data\zebra_etiqueta_config.json" "%INST%paquete\03_CONFIG\zebra_etiqueta_config.json" >nul

echo [BD] Dump (opcional)...
if not exist "%INST%paquete\01_BASE_DATOS" mkdir "%INST%paquete\01_BASE_DATOS"
set "PY=%REPO%\.venv\Scripts\python.exe"
if exist "%PY%" (
  "%PY%" "%REPO%\scripts\backup_neon_dump.py" --url-key DATABASE_URL --out-dir "%INST%paquete\01_BASE_DATOS" 2>nul
)

echo [CHK] Instaladores embebidos...
if not exist "%INST%paquete\00_POSTGRESQL\postgresql-*-windows-x64.exe" (
  echo [AVISO] Falta postgresql-*-windows-x64.exe en paquete\00_POSTGRESQL\
)
if not exist "%INST%paquete\00_PYTHON\python-*-amd64.exe" (
  echo [AVISO] Falta python-3.12*-amd64.exe en paquete\00_PYTHON\
)

echo.
echo [OK] Copie TODA la carpeta INSTALACION al USB/PC nuevo:
echo   %INST%
echo.
pause
exit /b 0
