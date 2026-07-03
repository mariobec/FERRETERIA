@echo off
REM Job Gmail DTE — etiquetar por RUT + importar SD al ERP (solo carpeta DTE, no todo INBOX)
setlocal
cd /d "%~dp0..\.."

set PY=%CD%\.venv\Scripts\pythonw.exe
if not exist "%PY%" set PY=%CD%\.venv\Scripts\python.exe
if not exist "%PY%" set PY=%CD%\venv\Scripts\pythonw.exe
if not exist "%PY%" set PY=%CD%\venv\Scripts\python.exe
set LOG_DIR=%CD%\logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

for /f "tokens=1-3 delims=/ " %%a in ('echo %date%') do set FECHA=%%c-%%b-%%a
set LOG=%LOG_DIR%\gmail_dte_job_%FECHA%.log

echo === %date% %time% gmail_dte_job ===>>"%LOG%"
echo Carpeta ERP: %CD%>>"%LOG%"

if not exist "%PY%" (
  echo ERROR: no existe venv: %PY%>>"%LOG%"
  exit /b 1
)

REM 1) Etiquetar correos que el filtro Gmail dejo en etiqueta DTE
"%PY%" scripts\lector_correo_dte.py --solo-etiquetar --carpeta-imap DTE --todos --recientes --limite 100 >>"%LOG%" 2>&1
set ERR1=%ERRORLEVEL%

REM 2) Importar al ERP solo recepciones documentales RUT 8054120-1
if exist "%CD%\.env.local" (
  "%PY%" scripts\lector_correo_dte.py --carpeta-imap DTE-8054120-1 --todos --recientes --limite 30 >>"%LOG%" 2>&1
  set ERR2=%ERRORLEVEL%
) else (
  echo AVISO: falta .env.local — solo etiquetado>>"%LOG%"
  set ERR2=0
)

echo Fin job ERR etiquetar=%ERR1% import=%ERR2%>>"%LOG%"
if %ERR1% GEQ 2 exit /b %ERR1%
if %ERR2% GEQ 2 exit /b %ERR2%
exit /b 0
