# Instala Playwright + Chromium para Radar Precios (Imperial.cl y sitios SPA).
# Ejecutar en PowerShell desde la carpeta del ERP, con el MISMO Python que usa Flask.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "Python:" (Get-Command python).Source
python -m pip install playwright certifi
python -m playwright install chromium
Write-Host ""
Write-Host "Listo. Reinicie Flask y vuelva a /precios/radar"
python -c "from services.radar_precios_fetch import playwright_chromium_listo; print('Chromium listo:', playwright_chromium_listo())"
