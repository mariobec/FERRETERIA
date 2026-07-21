@echo off
setlocal
title LhexIA - Ver error POS (ventana negra)

call "%~dp0_ir_raiz_erp.bat"
if errorlevel 1 pause & exit /b 1

echo.
echo ============================================
echo   Abra en el navegador:
echo   http://127.0.0.1:5000/punto_venta
echo.
echo   El traceback del error 500 aparece ABAJO
echo   en la ventana negra del ERP.
echo   Copielo y envielo.
echo ============================================
echo.

if not exist "%ERP_ROOT%.env.local" (
  echo [ERROR] Falta .env.local
  pause
  exit /b 1
)

cd /d "%ERP_ROOT%"
echo Modo diagnostico: errores visibles en navegador (FLASK_DEBUG=1)
set "FLASK_DEBUG=1"
"%ERP_ROOT%LhexIA_ERP.exe"
pause
