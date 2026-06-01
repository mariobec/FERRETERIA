@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

REM Instalador completo LhexIA tienda ??? codigo + datos
REM Copie esta carpeta a C:\LhexIA\_piloto\instalador_tienda_YYYYMMDD_HHMMSS
REM Repo destino: C:\LhexIA\ERP\sistema_ventas_limpio  (o C:\LhexIA\ERP)

for %%I in ("%~dp0..") do set "PACK=%%~fI"
if defined LHEXIA_REPO (
  set "REPO=%LHEXIA_REPO%"
) else (
  set "REPO=C:\LhexIA\ERP\sistema_ventas_limpio"
  if not exist "%REPO%\app.py" set "REPO=C:\LhexIA\ERP"
  if not exist "%REPO%\app.py" for %%I in ("%PACK%\..\..") do set "REPO=%%~fI"
)
if not exist "%REPO%\app.py" (
  echo ERROR: No encuentro app.py en %REPO%
  echo Clone el repo: git clone https://github.com/mariobec/FERRETERIA.git "%REPO%"
  pause & exit /b 1
)

for /f "tokens=1,* delims==" %%A in ('findstr /B "commit=" "%PACK%\03_INSTRUCCIONES\GIT_COMMIT.txt"') do set "GIT_COMMIT=%%B"
echo Pack: %PACK%
echo Repo: %REPO%
echo Commit objetivo: %GIT_COMMIT%
echo.

cd /d "%REPO%"

echo [1/6] Git fetch + checkout commit del instalador...
git fetch origin
if errorlevel 1 ( echo AVISO: git fetch fallo ??? revise red & exit /b 1 )
git checkout %GIT_COMMIT%
if errorlevel 1 (
  echo ERROR: checkout fallo. Ejecute: git fetch origin ^&^& git checkout %GIT_COMMIT%
  pause & exit /b 1
)

if exist "%PACK%\04_CODIGO\patch" (
  echo [2/6] Aplicando patch sin commit...
  xcopy /E /Y /I "%PACK%\04_CODIGO\patch\*" "%REPO%\"
) else (
  echo [2/6] Sin patch adicional
)

echo [3/6] Python .venv...
if exist ".venv\Scripts\python.exe" rmdir /s /q .venv
python -m venv .venv
if errorlevel 1 ( echo ERROR: python -m venv & pause & exit /b 1 )
".venv\Scripts\python.exe" -m pip install -r requirements.txt -q

echo [4/6] Restaurar base ferreteria_local...
set "DUMP="
for %%F in ("%PACK%\01_BASE_DATOS\piloto_sd_ferreteria_*.dump") do set "DUMP=%%F"
if not defined DUMP for %%F in ("%PACK%\01_BASE_DATOS\*.dump") do set "DUMP=%%F"
if not defined DUMP (
  echo ERROR: falta .dump en 01_BASE_DATOS
  pause & exit /b 1
)
call "%PACK%\03_INSTRUCCIONES\restaurar_piloto_tienda.bat" "!DUMP!"

echo [5/6] Config .env.local...
if exist "%PACK%\02_CONFIG\.env.local.template" (
  copy /Y "%PACK%\02_CONFIG\.env.local.template" "%REPO%\.env.local" >nul
  echo Copiado .env.local ??? ajuste DATABASE_URL localhost y PUBLIC_SITE_URL LAN
) else (
  echo AVISO: copie manualmente 02_CONFIG\.env.local.template
)

echo [6/6] Verificacion rapida...
".venv\Scripts\python.exe" -c "import app; print('import app OK')" 2>nul
if errorlevel 1 echo AVISO: import app fallo ??? revise dependencias

echo.
echo === Instalacion completa ===
echo Arrancar: %REPO%\arrancar_erp.bat
echo URL: http://localhost:5000
echo Smoke: caja SLA, POS, vitrina
pause
