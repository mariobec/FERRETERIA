# Reimporta todos los CSV RCV SII en Neon (misma BD que www.lhexia.cl / Render).
# Requiere: .env.local con NEON_DATABASE_URL y carpeta datos_rcv/
#
# Uso:
#   cd "d:\ERP FERRETERIA\PROYECTO FERRETERIA\sistema_ventas_limpio"
#   .\scripts\reimportar_rcv_neon_todos.ps1
#   .\scripts\reimportar_rcv_neon_todos.ps1 -DryRun

param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$rcvDir = Join-Path $Root "datos_rcv"
if (-not (Test-Path $rcvDir)) {
    Write-Error "No existe carpeta datos_rcv en $Root"
}

$archivos = Get-ChildItem (Join-Path $rcvDir "RCV_COMPRA_REGISTRO_*.csv") | Sort-Object Name
if ($archivos.Count -eq 0) {
    Write-Error "No hay archivos RCV_COMPRA_REGISTRO_*.csv en datos_rcv"
}

Write-Host "=== RCV SII -> Neon ===" -ForegroundColor Cyan
Write-Host "Archivos: $($archivos.Count)"
Write-Host "Modo: $(if ($DryRun) { 'DRY-RUN' } else { 'IMPORT REAL (--neon)' })"
Write-Host ""

$fallos = 0
foreach ($f in $archivos) {
    Write-Host "--- $($f.Name) ---" -ForegroundColor Yellow
    $args = @("scripts/importar_rcv_sii.py", "--neon", "-i", $f.FullName)
    if ($DryRun) { $args += "--dry-run" }
    & python @args
    if ($LASTEXITCODE -ne 0) {
        $fallos++
        Write-Host "ERROR en $($f.Name) (exit $LASTEXITCODE)" -ForegroundColor Red
    }
}

Write-Host ""
if ($fallos -eq 0) {
    Write-Host "OK: lote completado." -ForegroundColor Green
    Write-Host "Verifique en https://www.lhexia.cl/recepciones (filtro Pendiente de items)." -ForegroundColor Gray
} else {
    Write-Host "Fin con $fallos archivo(s) con error." -ForegroundColor Red
    exit 1
}
