@echo off
REM Job Gmail transferencias banco — etiquetar INBOX + sync bandeja caja ERP
setlocal
cd /d "%~dp0..\.."

set PY=%CD%\.venv\Scripts\pythonw.exe
if not exist "%PY%" set PY=%CD%\.venv\Scripts\python.exe
if not exist "%PY%" set PY=%CD%\venv\Scripts\pythonw.exe
if not exist "%PY%" set PY=%CD%\venv\Scripts\python.exe
set LOG_DIR=%CD%\logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

for /f "tokens=1-3 delims=/ " %%a in ('echo %date%') do set FECHA=%%c-%%b-%%a
set LOG=%LOG_DIR%\gmail_transferencias_job_%FECHA%.log

echo === %date% %time% gmail_transferencias_job ===>>"%LOG%"
echo Carpeta ERP: %CD%>>"%LOG%"

if not exist "%PY%" (
  echo ERROR: no existe python venv: %PY%>>"%LOG%"
  exit /b 1
)

if not exist "%CD%\.env.local" (
  echo AVISO: falta .env.local>>"%LOG%"
  exit /b 1
)

REM 1) Clasificar nuevos en INBOX (ventana corta — job cada 2 min)
"%PY%" scripts\setup_gmail_transferencias_correo.py --solo-etiquetar --limite 60 --dias 7 >>"%LOG%" 2>&1
set ERR1=%ERRORLEVEL%

REM 2) Sync carpeta Transferencias-Banco → BD bandeja caja
"%PY%" scripts\lector_correo_transferencias.py --limite 60 >>"%LOG%" 2>&1
set ERR2=%ERRORLEVEL%

echo Fin job ERR etiquetar=%ERR1% sync=%ERR2%>>"%LOG%"
if %ERR1% GEQ 2 exit /b %ERR1%
if %ERR2% GEQ 2 exit /b %ERR2%
exit /b 0
