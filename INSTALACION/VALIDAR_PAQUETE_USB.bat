@echo off
setlocal EnableDelayedExpansion
title LhexIA - Validar paquete USB

set "ROOT=%~dp0"
set "OK=1"
set "EXE_MODE=0"
if exist "%ROOT%erp\LhexIA_ERP.exe" set "EXE_MODE=1"

echo.
echo === Validacion carpeta INSTALACION (antes de copiar al USB) ===
echo   %ROOT%
echo.

if exist "%ROOT%erp\LhexIA_ERP.exe" (
  echo [OK] erp\LhexIA_ERP.exe
) else if exist "%ROOT%erp\app.py" (
  echo [OK] erp\app.py ^(modo legacy^)
) else (
  echo [FALLO] Falta erp\LhexIA_ERP.exe — ejecute COMPILAR_ERP_EXE.bat en DEV
  set "OK=0"
)

if exist "%ROOT%paquete\INSTALAR_LHEXIA.bat" (
  echo [OK] paquete\INSTALAR_LHEXIA.bat
) else (
  echo [FALLO] Falta paquete\INSTALAR_LHEXIA.bat
  set "OK=0"
)

set "PG=0"
for %%F in ("%ROOT%paquete\00_POSTGRESQL\postgresql-*-windows-x64.exe") do set "PG=1"
for %%F in ("%ROOT%paquete\00_POSTGRESQL\*.exe") do set "PG=1"
if "!PG!"=="1" (echo [OK] Postgres en paquete\00_POSTGRESQL\) else (
  echo [AVISO] Falta postgresql-*-windows-x64.exe en paquete\00_POSTGRESQL\
)

set "PY=0"
for %%F in ("%ROOT%paquete\00_PYTHON\python-*-amd64.exe") do set "PY=1"
if "!PY!"=="1" (
  echo [OK] Python en paquete\00_PYTHON\
) else if "!EXE_MODE!"=="1" (
  echo [OK] Python NO requerido ^(modo LhexIA_ERP.exe^)
) else (
  echo [AVISO] Falta python-3.12*-amd64.exe en paquete\00_PYTHON\ ^(modo legacy^)
)

set "DUMP=0"
for %%F in ("%ROOT%paquete\01_BASE_DATOS\*.dump") do set "DUMP=1"
if "!DUMP!"=="1" (echo [OK] Dump BD en paquete\01_BASE_DATOS\) else (
  echo [AVISO] Sin .dump — paso 4 fallara hasta generar dump en DEV
)

echo.
if "!OK!"=="0" (
  echo [RESULTADO] Paquete INCOMPLETO — no copiar al USB aun.
  echo.
  pause
  exit /b 1
)
echo [RESULTADO] Paquete listo. Copie TODA la carpeta INSTALACION al USB.
echo En PC nuevo: 00_Instalar_servidor_completo.bat
echo.
echo NO use carpetas viejas LhexIA_Instalador_SD ni 02_APLICACION.
echo.
pause
exit /b 0
