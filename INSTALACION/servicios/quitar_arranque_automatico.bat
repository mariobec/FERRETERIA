@echo off
setlocal
title LhexIA ERP - Quitar arranque automatico

schtasks /Delete /F /TN "LhexIA ERP Servidor" 2>nul
if errorlevel 1 (echo No existia la tarea.) else (echo [OK] Tarea eliminada.)
pause
exit /b 0
