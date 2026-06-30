@echo off
REM Unico acceso desde la raiz del repo de desarrollo
start "" "%~dp0INSTALACION\LhexIA_Centro_Control.exe" 2>nul || call "%~dp0INSTALACION\01_Centro_de_Control.bat"
