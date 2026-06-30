@echo off
setlocal EnableDelayedExpansion
title LhexIA ERP - Verificacion servicios

call "%~dp0_ir_raiz_erp.bat"
set "ROOT=%ERP_ROOT%"

echo.
echo ============================================
echo   Verificacion LhexIA ERP
echo   %DATE% %TIME%
echo ============================================
echo.

echo [1/5] PostgreSQL
set "PG_FOUND=0"
for /f "tokens=1" %%S in ('powershell -NoProfile -Command "Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name"') do (
  set "PG_FOUND=1"
  echo   %%S
)
if "!PG_FOUND!"=="0" echo   [FAIL] Sin servicio postgresql*
echo.

echo [2/5] Puerto 5432
netstat -ano | findstr /R /C:":5432 .*LISTENING" >nul && echo   [OK] || echo   [FAIL]
echo.

echo [3/5] Tarea arranque automatico
schtasks /Query /TN "LhexIA ERP Servidor" >nul 2>&1 && echo   [OK] || echo   [WARN] No registrada
echo.

echo [4/5] Puerto 5000 ERP
netstat -ano | findstr /R /C:":5000 .*LISTENING" >nul && echo   [OK] || echo   [WARN] ERP no activo
echo.

echo [5/5] HTTP /healthz
powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:5000/healthz' -UseBasicParsing -TimeoutSec 5).StatusCode } catch { 'FAIL' }"
echo.

if /I "%LHEXIA_RUNTIME_MODE%"=="exe" (
  if exist "%ROOT%LhexIA_ERP.exe" (echo Runtime: LhexIA_ERP.exe OK) else (echo Runtime: [FAIL] falta LhexIA_ERP.exe)
) else if exist "%ROOT%.venv\Scripts\python.exe" (
  echo Runtime: .venv OK
) else (
  echo Runtime: [FAIL] falta .venv o LhexIA_ERP.exe
)
echo.
pause
exit /b 0
