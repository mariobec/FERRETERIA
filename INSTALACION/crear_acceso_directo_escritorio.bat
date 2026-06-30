@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\crear_acceso_directo_centro_control.ps1" -ErpRoot "%~dp0." -InstalacionDir "%~dp0INSTALACION"
pause
