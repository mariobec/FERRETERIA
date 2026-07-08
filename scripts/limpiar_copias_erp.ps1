# LhexIA ERP — Eliminar copias duplicadas (dejar solo el sistema original DEV)
# ORIGINAL (NO SE BORRA):
#   C:\ERP FERRETERIA\PROYECTO FERRETERIA\sistema_ventas_limpio
param(
    [switch]$Ejecutar,
    [switch]$SoloListar
)

$Original = 'C:\ERP FERRETERIA\PROYECTO FERRETERIA\sistema_ventas_limpio'

$Duplicados = @(
    'C:\ERP FERRETERIA\PROYECTO FERRETERIA - resp-31-05-2026',
    'C:\ERP FERRETERIA\PROYECTO FERRETERIA 28-04-Ccredito',
    'C:\ERP FERRETERIA\PROYECTO FERRETERIA 28-04-factura',
    'C:\ERP FERRETERIA\PROYECTO FERRETERIA 29-04 punto venta',
    'C:\ERP FERRETERIA\PROYECTO FERRETERIA-28-04-2026',
    'C:\ERP FERRETERIA\PROYECTO FERRETERIA30-04-26 nube',
    'C:\ERP FERRETERIA\PROYECTO FERRETERIA\_DEPLOY_SERVIDOR_2026-07-03',
    'C:\ERP FERRETERIA\PROYECTO FERRETERIA\sistema_ventas_limpio_RESPALDO_2026-05-15_202116',
    'C:\ERP FERRETERIA\PROYECTO FERRETERIA\sistema_ventas',
    'C:\ERP FERRETERIA\PROYECTO FERRETERIA\DEMO_FERRETERIA_ERP',
    'C:\Users\mario\OneDrive\Documentos\GitHub\FERRETERIA'
)

Write-Host ''
Write-Host '============================================'
Write-Host '  LhexIA — Limpieza de copias duplicadas'
Write-Host '============================================'
Write-Host ''
Write-Host "ORIGINAL (se conserva):" -ForegroundColor Green
Write-Host "  $Original"
Write-Host ''
Write-Host 'DUPLICADOS (candidatos a borrar):' -ForegroundColor Yellow

$existentes = @()
foreach ($p in $Duplicados) {
    if (Test-Path -LiteralPath $p) {
        $existentes += $p
        Write-Host "  [EXISTE] $p"
    } else {
        Write-Host "  [no existe] $p" -ForegroundColor DarkGray
    }
}

if (-not $existentes) {
    Write-Host ''
    Write-Host 'No hay duplicados que borrar.'
    exit 0
}

if ($SoloListar -or -not $Ejecutar) {
    Write-Host ''
    Write-Host 'Modo simulacion. Para borrar de verdad:' -ForegroundColor Cyan
    Write-Host '  powershell -ExecutionPolicy Bypass -File scripts\limpiar_copias_erp.ps1 -Ejecutar'
    exit 0
}

Write-Host ''
$confirm = Read-Host 'Escriba BORRAR para eliminar las carpetas listadas'
if ($confirm -ne 'BORRAR') {
    Write-Host 'Cancelado.'
    exit 1
}

foreach ($p in $existentes) {
    Write-Host "Eliminando: $p"
    Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction Stop
    Write-Host '  [OK]'
}

Write-Host ''
Write-Host 'Limpieza completada. Sistema original intacto en:' -ForegroundColor Green
Write-Host "  $Original"
