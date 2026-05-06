@echo off
setlocal ENABLEDELAYEDEXPANSION
title ERP Ferreteria - Instalador DEMO cliente

echo ===============================================
echo   ERP Ferreteria - Paquete DEMO (cliente)
echo ===============================================
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] No se encontro Python Launcher (py).
  echo Instala Python 3.11+ desde https://www.python.org/downloads/
  pause
  exit /b 1
)

if not exist ".venv" (
  echo [1/4] Creando entorno virtual...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo [ERROR] No se pudo crear .venv
    pause
    exit /b 1
  )
) else (
  echo [1/4] Entorno virtual ya existe.
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
  echo [ERROR] No se pudo activar .venv
  pause
  exit /b 1
)

echo [2/4] Actualizando pip...
python -m pip install --upgrade pip
if errorlevel 1 (
  echo [ERROR] Fallo al actualizar pip.
  pause
  exit /b 1
)

echo [3/4] Instalando dependencias...
pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Fallo instalacion de dependencias.
  pause
  exit /b 1
)

if not exist ".env.demo" (
  echo [4/4] Copiando .env.demo desde plantilla...
  copy /Y "env.demo.ejemplo" ".env.demo" >nul
  echo       Edita ".env.demo" con usuario/clave/host MySQL y nombre de base.
) else (
  echo [4/4] .env.demo ya existe.
)

echo.
echo Instalacion de Python completada.
echo Siguiente: MySQL - crea la base (ver crear_mysql_bd_demo.sql y LEEME_INSTALACION_DEMO.txt).
echo Luego ejecuta: post_instalacion_demo.bat
echo Despues: iniciar_demo_windows.bat
echo.
pause
exit /b 0
