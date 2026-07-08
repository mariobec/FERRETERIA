@echo off
setlocal
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\scripts\crear_acceso_directo_centro_control.ps1" -RepoRoot "%~dp0.." -InstalacionDir "%~dp0"
pause
