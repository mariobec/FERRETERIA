# LhexIA ERP — arranque con entorno virtual (no usar "python app.py" suelto)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$py = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) {
    Write-Host ''
    Write-Host '[ERROR] Falta .venv — ejecute instalar_pruebas_windows.bat' -ForegroundColor Red
    Write-Host 'No use: python app.py  (no tiene Flask instalado)' -ForegroundColor Yellow
    Write-Host ''
    exit 1
}

$env:PGCLIENTENCODING = 'UTF8'
if (-not $env:FLASK_DEBUG) { $env:FLASK_DEBUG = '1' }

$listen = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue
if ($listen) {
    $pid5000 = $listen.OwningProcess | Select-Object -First 1
    Write-Host "[AVISO] Puerto 5000 ocupado (PID $pid5000). Cierre el otro servidor antes." -ForegroundColor Yellow
}

Write-Host ''
Write-Host '============================================' -ForegroundColor Cyan
Write-Host '  LhexIA ERP — http://127.0.0.1:5000' -ForegroundColor Cyan
Write-Host "  Python: $py" -ForegroundColor DarkGray
Write-Host '  Detener: Ctrl+C' -ForegroundColor Cyan
Write-Host '============================================' -ForegroundColor Cyan
Write-Host ''

& $py app.py
