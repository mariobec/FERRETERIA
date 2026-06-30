@echo off
REM Carpeta INSTALACION autocontenida: erp\ = aplicacion (exe o fuente)
for %%I in ("%~dp0..") do set "INSTALACION_ROOT=%%~fI"
set "ERP_ROOT=%INSTALACION_ROOT%\erp"

if exist "%ERP_ROOT%\LhexIA_ERP.exe" (
  cd /d "%ERP_ROOT%"
  set "LHEXIA_INSTALACION=%INSTALACION_ROOT%"
  set "LHEXIA_RUNTIME_MODE=exe"
  exit /b 0
)

if exist "%ERP_ROOT%\app.py" (
  cd /d "%ERP_ROOT%"
  set "LHEXIA_INSTALACION=%INSTALACION_ROOT%"
  set "LHEXIA_RUNTIME_MODE=source"
  exit /b 0
)

REM Desarrollo: si aun no empaqueto erp\, usar repo padre
for %%I in ("%INSTALACION_ROOT%\..") do set "DEV_ROOT=%%~fI"
if exist "%DEV_ROOT%\app.py" (
  set "ERP_ROOT=%DEV_ROOT%"
  cd /d "%ERP_ROOT%"
  set "LHEXIA_INSTALACION=%INSTALACION_ROOT%"
  set "LHEXIA_RUNTIME_MODE=dev"
  exit /b 0
)

echo [ERROR] No hay aplicacion en %INSTALACION_ROOT%\erp
echo Ejecute COMPILAR_ERP_EXE.bat o EMPAQUETAR_desde_DEV.bat
cd /d "%INSTALACION_ROOT%"
exit /b 1
