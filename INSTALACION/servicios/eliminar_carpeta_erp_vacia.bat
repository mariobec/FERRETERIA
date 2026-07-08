@echo off
REM Elimina INSTALACION\erp vacia (contenido ya archivado en BACKUPS)
set "ERP_DIR=%~dp0..\erp"
if not exist "%ERP_DIR%" (
  echo [OK] Ya no existe erp\
  exit /b 0
)
dir /a "%ERP_DIR%" | findstr /v /c:"<DIR>          ." | findstr /v /c:"<DIR>          .." | findstr /r /c:"[0-9][0-9].*archivos" >nul
for /f "tokens=1" %%A in ('dir /a "%ERP_DIR%" ^| findstr /r "archivos.*bytes"') do set N=%%A
rmdir "%ERP_DIR%" 2>nul && (
  echo [OK] Carpeta erp\ eliminada.
  exit /b 0
)
echo [AVISO] Cierre Cursor/LhexIA Control y vuelva a ejecutar este script.
pause
exit /b 1
