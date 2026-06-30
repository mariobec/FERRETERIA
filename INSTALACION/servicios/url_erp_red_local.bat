@echo off
setlocal EnableDelayedExpansion
title LhexIA ERP - URL tablets

call "%~dp0_ir_raiz_erp.bat"

echo.
echo ============================================
echo   URL para tablets / otros PCs en la WiFi
echo ============================================
echo.

set "FIJA="
if /I "%LHEXIA_RUNTIME_MODE%"=="exe" (
  for /f "delims=" %%U in ('"%ERP_ROOT%LhexIA_ERP.exe" url-red --mostrar 2^>nul') do set "FIJA=%%U"
) else (
  set "VENV_PY=%ERP_ROOT%.venv\Scripts\python.exe"
  if not exist "%VENV_PY%" set "VENV_PY=python"
  for /f "delims=" %%U in ('"%VENV_PY%" "%ERP_ROOT%scripts\configurar_url_red_erp.py" --mostrar 2^>nul') do set "FIJA=%%U"
)

if defined FIJA (
  echo !FIJA! | findstr /I "sin URL fija" >nul
  if errorlevel 1 (
    echo URL fija:
    echo   !FIJA!/login
    goto :fin
  )
)

echo IP actual:
powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' -and $_.IPAddress -notlike '169.254.*' } | ForEach-Object { '  http://' + $_.IPAddress + ':5000/login' }"

:fin
echo.
echo En este PC: http://127.0.0.1:5000/login
echo.
pause
exit /b 0
