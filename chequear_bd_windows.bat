@echo off
chcp 65001 >nul
title ERP - Chequear base de datos vs codigo
cd /d "%~dp0"

echo ============================================
echo   Chequeo: modelo Python vs tu MySQL
echo ============================================
echo.

if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
) else (
  echo [AVISO] No hay carpeta .venv - se usa el Python del sistema.
  echo          Si falla "import app", ejecuta antes instalar_pruebas_windows.bat
  echo.
)

if exist "env_qa.txt" (
  echo Leyendo configuracion desde env_qa.txt ...
  for /f "usebackq tokens=1,* delims==" %%A in ("env_qa.txt") do (
    if not "%%A"=="" if /i not "%%A:~0,1%%"=="#" set "%%A=%%B"
  )
)
if exist ".env.qa" (
  echo Leyendo configuracion desde .env.qa ...
  for /f "usebackq tokens=1,* delims==" %%A in (".env.qa") do (
    if not "%%A"=="" if /i not "%%A:~0,1%%"=="#" set "%%A=%%B"
  )
)

if "%SQLALCHEMY_DATABASE_URI%"=="" (
  echo [ERROR] No esta definida SQLALCHEMY_DATABASE_URI.
  echo.
  echo Crea el archivo env_qa.txt en esta carpeta ^(se ve en el Explorador^) con una linea:
  echo   SQLALCHEMY_DATABASE_URI=mysql+pymysql://TU_USUARIO:TU_CLAVE@localhost/TU_BASE
  echo O ejecuta CREAR_ENV_QA.bat ^(crea env_qa.txt y lo abre en el Bloc de notas^).
  echo.
  pause
  exit /b 1
)

echo Ejecutando chequeo...
echo.
python chequear_esquema_bd.py %*
set ERR=%errorlevel%
echo.
if %ERR% neq 0 (
  echo Si quieres ver sugerencias ALTER, cierra esta ventana y ejecuta:
  echo   chequear_bd_windows.bat --sugerir-sql
)
pause
exit /b %ERR%
