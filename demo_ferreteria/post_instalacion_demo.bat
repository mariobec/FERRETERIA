@echo off
setlocal ENABLEDELAYEDEXPANSION
title ERP Ferreteria - Crear tablas y usuario admin DEMO

if not exist ".venv\Scripts\activate.bat" (
  echo [ERROR] Ejecuta primero instalar_demo_windows.bat
  pause
  exit /b 1
)

if not exist ".env.demo" (
  echo [ERROR] Falta .env.demo. Copia env.demo.ejemplo a .env.demo y edita MySQL.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
for /f "usebackq tokens=1,* delims==" %%A in (".env.demo") do (
  if not "%%A"=="" if /i not "%%A:~0,1%%"=="#" set "%%A=%%B"
)

echo [1/2] Creando tablas desde modelos (SQLAlchemy)...
python crear_tablas_demo.py
if errorlevel 1 (
  echo [ERROR] Fallo crear_tablas_demo.py. Revisa que la base exista y la URI en .env.demo.
  pause
  exit /b 1
)

echo [2/2] Roles y usuario administrador (ADMIN_EMAIL / ADMIN_PASSWORD en .env.demo)...
python bootstrap_admin_local.py
if errorlevel 1 (
  echo [ERROR] Fallo bootstrap_admin_local.py
  pause
  exit /b 1
)

echo.
echo Listo. Inicia el sistema con iniciar_demo_windows.bat
echo.
pause
exit /b 0
