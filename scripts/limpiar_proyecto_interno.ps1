# Limpieza interna sistema_ventas_limpio (tras respaldo TEMP)
# Respaldo: BACKUPS\TEMP_sistema_ventas_limpio_2026-07-08_1236
param(
    [switch]$Ejecutar
)

$Root = 'C:\ERP FERRETERIA\PROYECTO FERRETERIA\sistema_ventas_limpio'
$Archivo = 'C:\ERP FERRETERIA\PROYECTO FERRETERIA\BACKUPS\ARCHIVO_interno_sistema_ventas_limpio_2026-07-08'

Set-Location $Root

function Move-Archivo($rel) {
    $src = Join-Path $Root $rel
    if (-not (Test-Path -LiteralPath $src)) { return }
    $dst = Join-Path $Archivo $rel
    $parent = Split-Path $dst -Parent
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    Write-Host "[MOVER] $rel"
    if ($Ejecutar) { Move-Item -LiteralPath $src -Destination $dst -Force }
}

function Remove-ItemRel($rel) {
    $p = Join-Path $Root $rel
    if (-not (Test-Path -LiteralPath $p)) { return }
    Write-Host "[BORRAR] $rel"
    if ($Ejecutar) { Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue }
}

Write-Host '=== Limpieza interna sistema_ventas_limpio ==='
Write-Host "Archivo externo: $Archivo"
Write-Host ''

# --- Mover carpetas pesadas / históricas fuera del repo ---
@(
    'respaldos',
    'instalador_intranet',
    'release',
    'INSTALACION\erp',
    'demo_ferreteria',
    '_backup_antes_pull',
    'backups',
    'liz',
    'Logos',
    'Imprimir'
) | ForEach-Object { Move-Archivo $_ }

# --- Artefactos regenerables ---
@(
    'build',
    'dist',
    '.venv.roto_20260525',
    'venv'
) | ForEach-Object { Remove-ItemRel $_ }

# --- Archivos basura / temporales en raíz ---
@(
    'USB005',
    'ZDesigner GX420d',
    'Generated_image.png',
    '_patch_stock_cat.py',
    'terminal_flask.log',
    'terminal_flask_err.log',
    'tmp_caja_vale_sla.log',
    'caja_vale_sla.log',
    'catalogo_fase_b.log',
    '_tmp_exe_out.txt',
    '_tmp_exe_err.txt',
    '~WRL0005.tmp'
) | ForEach-Object { Remove-ItemRel $_ }

Get-ChildItem -LiteralPath $Root -Filter '~$*' -File -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "[BORRAR] $($_.Name)"
    if ($Ejecutar) { Remove-Item -LiteralPath $_.FullName -Force }
}

# --- Docs redundantes en raíz (canónicos en docs/ o MANUALES/) ---
$docsMover = @{
    'VITRINA_OLLAMA_PRODUCCION.md' = 'docs\despliegue\VITRINA_OLLAMA_PRODUCCION.md'
    'CHILEMAT_CARGAS_LOCAL.md'     = 'docs\CHILEMAT_CARGAS_LOCAL.md'
    'PLAN_ECOM_PILOTO_v0.md'       = 'docs\planes\02-producto-lhexia\PLAN_ECOM_PILOTO_v0.md'
}
foreach ($pair in $docsMover.GetEnumerator()) {
    $src = Join-Path $Root $pair.Key
    $dst = Join-Path $Root $pair.Value
    if ((Test-Path -LiteralPath $src) -and -not (Test-Path -LiteralPath $dst)) {
        Write-Host "[REUBICAR] $($pair.Key) -> $($pair.Value)"
        if ($Ejecutar) {
            New-Item -ItemType Directory -Path (Split-Path $dst -Parent) -Force | Out-Null
            Move-Item -LiteralPath $src -Destination $dst -Force
        }
    }
}

@(
    'PLAN_CLAUDE_INTEGRACION.md',
    'PLAN_FACTURA_DETALLE_COMPRAS_SD1.md',
    'PLAN_PENDIENTES_DESARROLLO.md',
    'PLAN_PORTAL_EJECUTIVO_SD_CONSTRUCTOR.md',
    'PLAN_REFACTOR_OLEADA1_VENTA_CAJA.md',
    'PLAN_TRANSPORTE_RESPALDO_PRD.md',
    'PLAN_ECOM_PILOTO_v0.md',
    'REVERT_MAESTRA_FASE_A.md',
    'REVERT_MAESTRA_FASE_B.md',
    'REVERT_MAESTRA_FASE_C.md',
    'REVERT_MENU.md',
    'DOCUMENTACION_AUDITORIA.md',
    'memory.md',
    'PC_NUEVA_LISTA.md',
    'MAESTRA_COMPLETAR_BASE.md',
    'LHEXIA_BOOK.md',
    'LHEXIA_RADAR_PRECIO_EQUIPO.md',
    'DEPLOY_GRATIS_PRUEBAS.md',
    'PROPUESTA_COMERCIAL_ERP.md',
    'INSTALADOR_LHEXIA_ERP.md',
    'MANUAL_OPERATIVO_MODULOS.md',
    'GUIA_CARGA_5000_PRODUCTOS.md',
    'GUIA_INSTALACION_CLIENTE.md',
    'CONTRATO_BASE_SERVICIO_ERP.md',
    'COTIZACION_ERP_TEMPLATE.md'
) | ForEach-Object { Remove-ItemRel $_ }

# --- __pycache__ ---
if ($Ejecutar) {
    Get-ChildItem -LiteralPath $Root -Directory -Recurse -Filter '__pycache__' -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
    Write-Host '[BORRAR] __pycache__ (recursivo)'
} else {
    Write-Host '[BORRAR] __pycache__ (recursivo)'
}

Write-Host ''
if (-not $Ejecutar) {
    Write-Host 'Simulacion. Ejecutar con -Ejecutar'
} else {
    Write-Host 'Limpieza interna completada.'
}
