@echo off
REM Acceso directo: instalador vive en paquete\
cd /d "%~dp0paquete"
if not exist "%~dp0paquete\INSTALAR_LHEXIA.bat" (
  echo [ERROR] Falta carpeta paquete\ dentro de INSTALACION
  pause
  exit /b 1
)
call "%~dp0paquete\INSTALAR_LHEXIA.bat" %*
