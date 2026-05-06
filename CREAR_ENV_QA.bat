@echo off
chcp 65001 >nul
title Crear configuracion env_qa.txt
cd /d "%~dp0"

if exist "env_qa.txt" (
  echo Ya existe env_qa.txt en esta carpeta ^(deberias verlo en el Explorador^).
  echo Ruta: %CD%\env_qa.txt
  echo Abriendo en el Bloc de notas...
  start "" notepad "env_qa.txt"
  pause
  exit /b 0
)

if exist ".env.qa" (
  echo Ya existe .env.qa - el ERP tambien lo lee. Abriendo...
  start "" notepad ".env.qa"
  pause
  exit /b 0
)

echo Creando env_qa.txt en: %CD%
(
  echo # Edita la linea de abajo: usuario, clave y nombre de base MySQL
  echo SQLALCHEMY_DATABASE_URI=mysql+pymysql://USUARIO:CLAVE@localhost/ferreteria
  echo SECRET_KEY=qa-ferreteria-secret
  echo FLASK_DEBUG=0
  echo FLASK_TEMPLATE_RELOAD=0
  echo MARGEN_MINIMO_RECEPCION=0.18
) > "env_qa.txt"

echo.
echo LISTO. Archivo: %CD%\env_qa.txt
echo Cambia USUARIO, CLAVE y ferreteria por tus datos. Guarda y cierra.
echo.
start "" notepad "env_qa.txt"
pause
exit /b 0
