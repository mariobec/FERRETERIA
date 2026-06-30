@echo off
setlocal
title LhexIA ERP - Firewall puerto 5000

call "%~dp0_ir_raiz_erp.bat"

net session >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Clic derecho -^> Ejecutar como administrador
  pause
  exit /b 1
)

netsh advfirewall firewall delete rule name="LhexIA ERP TCP 5000" >nul 2>&1
netsh advfirewall firewall add rule name="LhexIA ERP TCP 5000" dir=in action=allow protocol=TCP localport=5000 profile=private,public,domain enable=yes

if errorlevel 1 (
  echo [ERROR] No se pudo crear la regla de firewall.
  pause
  exit /b 1
)

echo [OK] Puerto 5000 abierto en firewall.
pause
exit /b 0
