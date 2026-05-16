<#
.SYNOPSIS
  Respaldo ZIP del proyecto LhexIA ERP (código + config de ejemplo + historial git opcional).

.DESCRIPTION
  Genera un .zip junto a la carpeta del repo (por defecto en ../RESPALDOS_LHEXIA/).
  Usa `tar` integrado en Windows 10/11. La BASE DE DATOS no va dentro del ZIP: expórtela aparte
  (ver docs/RESPALDO_PROYECTO.md).

.PARAMETER RutaProyecto
  Raíz del repo (donde está app.py). Por defecto: carpeta padre de este script.

.PARAMETER CarpetaDestino
  Dónde guardar el ZIP. Por defecto: <padre del repo>/RESPALDOS_LHEXIA/

.PARAMETER SinHistorialGit
  Si se indica, excluye la carpeta .git (ZIP más liviano, sin commits).

.PARAMETER OmitirDtesEmitidos
  Excluye storage/dtes/emitidos (XML firmados pueden ser voluminosos).

.EXAMPLE
  .\scripts\backup_proyecto_completo.ps1

.EXAMPLE
  .\scripts\backup_proyecto_completo.ps1 -SinHistorialGit -OmitirDtesEmitidos
#>
[CmdletBinding()]
param(
    [string] $RutaProyecto = "",
    [string] $CarpetaDestino = "",
    [switch] $SinHistorialGit,
    [switch] $OmitirDtesEmitidos
)

$ErrorActionPreference = "Stop"

if (-not $RutaProyecto) {
    $RutaProyecto = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}
if (-not (Test-Path -LiteralPath (Join-Path $RutaProyecto "app.py"))) {
    Write-Error "No se encontró app.py en: $RutaProyecto (¿es la raíz del repo?)"
}

if (-not $CarpetaDestino) {
    $padre = Split-Path -Parent $RutaProyecto
    $CarpetaDestino = Join-Path $padre "RESPALDOS_LHEXIA"
}
New-Item -ItemType Directory -Force -Path $CarpetaDestino | Out-Null

$marca = Get-Date -Format "yyyyMMdd_HHmmss"
$nombreCarpeta = Split-Path -Leaf $RutaProyecto
$zipNombre = "${nombreCarpeta}_respaldo_${marca}.zip"
$rutaZip = Join-Path $CarpetaDestino $zipNombre

$tar = Get-Command tar -ErrorAction SilentlyContinue
if (-not $tar) {
    Write-Error "No está disponible 'tar' en PATH. Instale herramientas modernas de Windows o use 7-Zip manualmente."
}

# Exclusiones: basura de entorno y cachés (el código y plantillas sí van).
$excl = @(
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov",
    ".venv",
    "venv",
    "ENV",
    ".coverage"
)
if ($SinHistorialGit) { $excl += ".git" }
if ($OmitirDtesEmitidos) { $excl += "storage/dtes/emitidos" }

$args = @("-c", "-a", "-f", $rutaZip)
foreach ($e in $excl) {
    $args += "--exclude=$e"
}
$args += "."

Write-Host "Origen : $RutaProyecto"
Write-Host "Destino: $rutaZip"
Write-Host "Excluye: $($excl -join ', ')"

Push-Location $RutaProyecto
try {
    & tar @args
    if ($LASTEXITCODE -ne 0) {
        Write-Error "tar terminó con código $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

$mb = [math]::Round((Get-Item -LiteralPath $rutaZip).Length / 1MB, 2)
Write-Host ""
Write-Host "OK. Tamaño aproximado: $mb MB"
Write-Host "Recuerde: respaldo de PostgreSQL es aparte (pg_dump). Ver docs/RESPALDO_PROYECTO.md"
