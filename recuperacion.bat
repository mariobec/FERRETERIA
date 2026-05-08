@echo off
setlocal

cd /d "%~dp0"
echo.
echo === RECUPERACION RAPIDA (LOCAL + REMOTO) ===
echo.

git status -sb
echo.

git add -A
git reset -- "backups/ferreteria_local_20260507_192057.dump"

git commit -m "wip: recuperacion rapida" 2>nul
if %errorlevel%==0 (
  echo Commit creado.
) else (
  echo No habia cambios nuevos para commitear.
)

git push origin main
echo.
echo Proceso finalizado.
pause
