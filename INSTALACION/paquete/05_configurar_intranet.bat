@echo off
setlocal
title LhexIA - [5/5] Accesos e intranet

set "PACK=%~dp0"
call "%PACK%instalador.defaults.bat"

echo.
echo === Paso 5/5 - Accesos directos ===
echo.

set "INST=%INSTALACION_ROOT%"
powershell -NoProfile -Command ^
  "$d=$env:USERPROFILE+'\Desktop';" ^
  "$s1=(New-Object -ComObject WScript.Shell).CreateShortcut($d+'\LhexIA ERP.lnk');" ^
  "$s1.TargetPath='%INST%\02_Iniciar_ERP.bat'; $s1.WorkingDirectory='%INST%'; $s1.Save();" ^
  "$s2=(New-Object -ComObject WScript.Shell).CreateShortcut($d+'\LhexIA Centro de Control.lnk');" ^
  "$s2.TargetPath='%INST%\LhexIA_Centro_Control.exe'; $s2.WorkingDirectory='%INST%'; $s2.Save()"

echo [OK] Accesos en escritorio.
if exist "%INSTALACION_ROOT%erp\LhexIA_ERP.exe" (
  echo [OK] ERP en modo ejecutable — NO necesita carpeta .venv
) else (
  echo [INFO] Modo legacy: requiere .venv en erp\ ^(paso 3^).
)
echo Siguiente ^(admin^): ..\03_Configurar_intranet.bat
exit /b 0
