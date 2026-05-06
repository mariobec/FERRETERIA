@echo off
setlocal ENABLEDELAYEDEXPANSION
title ERP Ferreteria - Instalador de pruebas
cd /d "%~dp0"

echo ===============================================
echo   ERP Ferreteria - Instalador de pruebas (QA)
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
  echo [1/5] Creando entorno virtual...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo [ERROR] No se pudo crear .venv
    pause
    exit /b 1
  )
) else (
  echo [1/5] Entorno virtual ya existe.
)

echo [2/5] Activando entorno virtual...
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
  echo [ERROR] No se pudo activar .venv
  pause
  exit /b 1
)

echo [3/5] Actualizando pip...
python -m pip install --upgrade pip
if errorlevel 1 (
  echo [ERROR] Fallo al actualizar pip.
  pause
  exit /b 1
)

echo [4/5] Instalando dependencias...
pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Fallo instalacion de dependencias.
  pause
  exit /b 1
)

if not exist "env_qa.txt" if not exist ".env.qa" (
  echo [5/5] Creando env_qa.txt ^(se ve en el Explorador; edita usuario/clave/base^)...
  (
    echo # Configuracion local — mismo contenido que antes en .env.qa
    echo SQLALCHEMY_DATABASE_URI=mysql+pymysql://USUARIO:CLAVE@localhost/ferreteria
    echo SECRET_KEY=qa-ferreteria-secret
    echo FLASK_DEBUG=0
    echo FLASK_TEMPLATE_RELOAD=0
    echo MARGEN_MINIMO_RECEPCION=0.18
  ) > "env_qa.txt"
  echo       Ruta: %CD%\env_qa.txt
) else (
  echo [5/5] Ya existe env_qa.txt o .env.qa en: %CD%
)

echo.
echo Instalacion completada.
echo - Edita "%CD%\env_qa.txt" ^(o .env.qa^) con los datos reales de MySQL.
echo - Luego ejecuta "iniciar_pruebas_windows.bat"
echo.
pause
exit /b 0
