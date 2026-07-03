@echo off
REM Carga DTE Gmail - ano 2026 completo (por lotes de 200)
setlocal
cd /d "%~dp0..\.."
set PY=%CD%\venv\Scripts\python.exe
set LOG_DIR=%CD%\logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set LOG=%LOG_DIR%\migracion_dte_2026.log
set LOTE=200

echo === %date% %time% migracion DTE 2026 ===>>"%LOG%"
"%PY%" scripts\lector_correo_dte.py --desde 2026-01-01 --hasta 2027-01-01 --todos --recientes --limite %LOTE% -v >>"%LOG%" 2>&1
echo exit=%ERRORLEVEL%>>"%LOG%"
exit /b %ERRORLEVEL%
