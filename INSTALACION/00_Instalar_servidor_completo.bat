@echo off
title Instalar servidor LhexIA (PC nuevo)

if exist "%~dp0paquete\INSTALAR_LHEXIA.bat" (
  call "%~dp0paquete\INSTALAR_LHEXIA.bat" %*
  exit /b %errorlevel%
)

echo [ERROR] Falta paquete\INSTALAR_LHEXIA.bat
pause
exit /b 1
