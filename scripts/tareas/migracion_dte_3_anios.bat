@echo off
REM Migracion historica DTE ultimos 3 anos (INBOX, por lotes)
REM - Etiqueta por RUT (8054120-1 / otra sociedad)
REM - Importa al ERP solo SD (recepcion documental, sin stock)
REM - NO marca correos como leidos
REM - Repite hasta agotar lote o Ctrl+C
REM
REM Uso:
REM   migracion_dte_3_anios.bat           -> solo etiquetar (fase 1)
REM   migracion_dte_3_anios.bat importar  -> importar carpeta DTE-8054120-1 (fase 2)
REM   migracion_dte_3_anios.bat todo      -> etiquetar + importar por lote

setlocal
cd /d "%~dp0..\.."
set PY=%CD%\venv\Scripts\python.exe
set LOG_DIR=%CD%\logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set LOG=%LOG_DIR%\migracion_dte_3anios.log
set LOTE=200
set ANIOS=3
set MODO=%~1

if not exist "%PY%" (
  echo ERROR: venv no encontrado>>"%LOG%"
  exit /b 1
)

echo === %date% %time% migracion DTE %ANIOS% anios modo=%MODO% ===>>"%LOG%"

if /i "%MODO%"=="importar" goto fase2
if /i "%MODO%"=="todo" goto fase_both

:fase1
echo --- Fase 1: etiquetar INBOX (lote %LOTE%) --->>"%LOG%"
"%PY%" scripts\lector_correo_dte.py --historial-anios %ANIOS% --solo-etiquetar --recientes --limite %LOTE% -v >>"%LOG%" 2>&1
echo Fase1 exit=%ERRORLEVEL%>>"%LOG%"
exit /b %ERRORLEVEL%

:fase2
echo --- Fase 2: importar DTE-8054120-1 (lote 100) --->>"%LOG%"
"%PY%" scripts\lector_correo_dte.py --carpeta-imap DTE-8054120-1 --todos --recientes --limite 100 --no-marcar-leidos -v >>"%LOG%" 2>&1
echo Fase2 exit=%ERRORLEVEL%>>"%LOG%"
exit /b %ERRORLEVEL%

:fase_both
echo --- Lote combinado etiquetar+import --->>"%LOG%"
"%PY%" scripts\lector_correo_dte.py --historial-anios %ANIOS% --recientes --limite 100 -v >>"%LOG%" 2>&1
echo Todo exit=%ERRORLEVEL%>>"%LOG%"
exit /b %ERRORLEVEL%
