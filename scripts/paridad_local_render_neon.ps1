<#
.SYNOPSIS
  Comprueba que .env.local tenga las mismas claves que Render (paridad código + Neon).

.DESCRIPTION
  Modo recomendado "todo igual": DATABASE_URL en .env.local = misma URL Neon que en Render.
  Lista qué variables faltan en .env.local respecto a render.yaml y avisa sobre SECRET_KEY
  (TV cliente / tokens: conviene el MISMO valor en PC y Render).

.PARAMETER RutaRaiz
  Carpeta del repo (donde está app.py). Por defecto: padre de scripts/.

.PARAMETER RunInitDb
  Tras la revisión, ejecuta init_db.py contra Neon/URL de .env.local (init_neon_desde_local.ps1).

.EXAMPLE
  .\scripts\paridad_local_render_neon.ps1

.EXAMPLE
  .\scripts\paridad_local_render_neon.ps1 -RunInitDb
#>
[CmdletBinding()]
param(
    [string] $RutaRaiz = "",
    [switch] $RunInitDb
)

$ErrorActionPreference = "Stop"
if (-not $RutaRaiz) {
    $RutaRaiz = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Get-EnvValueFromFile {
    param([string]$Path, [string]$Key)
    if (-not (Test-Path -LiteralPath $Path)) { return "" }
    $pattern = "^\s*$([regex]::Escape($Key))\s*=\s*(.+)\s*$"
    foreach ($line in Get-Content -LiteralPath $Path -Encoding utf8) {
        if ($line -match '^\s*#' -or $line -notmatch '\S') { continue }
        if ($line -match $pattern) {
            $v = $Matches[1].Trim()
            if ($v.Length -ge 2 -and (($v[0] -eq $v[-1] -and $v[0] -eq '"') -or ($v[0] -eq $v[-1] -and $v[0] -eq "'"))) {
                $v = $v.Substring(1, $v.Length - 2)
            }
            return $v
        }
    }
    return ""
}

function Mask-DbHost {
    param([string]$Url)
    if (-not $Url) { return "(vacio)" }
    if ($Url -match '@([^/:@]+)') { return $Matches[1] }
    return "(no se pudo parsear host)"
}

# Claves declaradas en render.yaml (sync: false o con value) - mantener alineado con ese archivo.
$renderYamlKeys = @(
    @{ Key = "DATABASE_URL";        Required = $true;  Note = "Neon (pooler + sslmode=require). Misma URL en Render y .env.local para paridad total." }
    @{ Key = "BOOTSTRAP_ADMIN_EMAIL";   Required = $false; Note = "init_db.py crea admin si no existe." }
    @{ Key = "BOOTSTRAP_ADMIN_PASSWORD"; Required = $false; Note = "Obligatorio si usas email bootstrap." }
    @{ Key = "BOOTSTRAP_ADMIN_NAME";     Required = $false; Note = "Opcional." }
    @{ Key = "PUBLIC_SITE_URL";   Required = $true;  Note = "Render: https://tu-servicio.onrender.com | Local: http://127.0.0.1:5000" }
    @{ Key = "SECRET_KEY";        Required = $false; Note = "Mismo valor que Render (dashboard) para TV / Live Wall." }
    @{ Key = "FLASK_DEBUG";       Required = $false; Note = "Render suele 0; local puede 1 solo en desarrollo." }
    @{ Key = "PUBLICO_MUESTRA_PRECIO";       Required = $false; Note = "0 en render.yaml; igual en .env.local para catalogo publico." }
    @{ Key = "PUBLICO_MUESTRA_STOCK_EXACTO"; Required = $false; Note = "0 en render.yaml." }
    @{ Key = "EMPRESA_NOMBRE_COMERCIAL"; Required = $false; Note = "Opcional en render.yaml; mismo texto que en local." }
    @{ Key = "EMPRESA_RUT";        Required = $false; Note = "Opcional; facturacion / cabeceras." }
)

$envLocal = Join-Path $RutaRaiz ".env.local"
$envExample = Join-Path $RutaRaiz ".env.example"

Write-Host ""
Write-Host "=== Paridad local / Render / Neon ===" -ForegroundColor Cyan
Write-Host "Raiz: $RutaRaiz"
Write-Host ""

if (-not (Test-Path -LiteralPath $envLocal)) {
    Write-Host '[!] No existe .env.local' -ForegroundColor Yellow
    Write-Host "    Copiá .env.example -> .env.local y completá al menos DATABASE_URL (Neon) y SECRET_KEY."
    if (Test-Path -LiteralPath $envExample) {
        Write-Host "    Ejemplo: Copy-Item .env.example .env.local"
    }
    exit 1
}

$db = (Get-EnvValueFromFile -Path $envLocal -Key "DATABASE_URL").Trim()
$neonAlt = (Get-EnvValueFromFile -Path $envLocal -Key "NEON_DATABASE_URL").Trim()

Write-Host "DATABASE_URL host: $(Mask-DbHost -Url $db)"
if ($neonAlt) {
    Write-Host "NEON_DATABASE_URL host (scripts): $(Mask-DbHost -Url $neonAlt)"
}

if ($db -match 'neon\.tech|neon\.(tech|serverless)') {
    Write-Host "Modo: parece apuntar a Neon (paridad datos con Render si usan la misma URL)." -ForegroundColor Green
}
elseif ($db -match 'localhost|127\.0\.0\.1') {
    Write-Host "Modo: Postgres local. Render sigue en Neon - datos distintos salvo sync manual (ver docs/MIGRACION_RENDER_NEON.md)." -ForegroundColor Yellow
}
elseif (-not $db) {
    Write-Host '[!] DATABASE_URL vacio en .env.local' -ForegroundColor Red
}

Write-Host ""
Write-Host "--- Variables (presente en .env.local = OK) ---" -ForegroundColor Cyan

$missingRequired = @()
foreach ($row in $renderYamlKeys) {
    $k = $row.Key
    $val = (Get-EnvValueFromFile -Path $envLocal -Key $k).Trim()
    $ok = $val.Length -gt 0
    $tag = if ($ok) { "[OK]" } else { "[--]" }
    $color = if ($ok) { "Green" } elseif ($row.Required) { "Red" } else { "Yellow" }
    Write-Host ("$tag  {0,-38} {1}" -f $k, $row.Note) -ForegroundColor $color
    if (-not $ok -and $row.Required) {
        $missingRequired += $k
    }
}

Write-Host ""
if ($missingRequired.Count -gt 0) {
    Write-Host "Faltan obligatorias en .env.local: $($missingRequired -join ', ')" -ForegroundColor Red
}
else {
    Write-Host "Todas las claves marcadas como requeridas están definidas en .env.local." -ForegroundColor Green
}

Write-Host ""
Write-Host "Recordatorio SECRET_KEY:" -ForegroundColor Cyan
Write-Host "  Si Render generó SECRET_KEY automáticamente, copialo del dashboard a .env.local"
Write-Host "  para que tokens de TV cliente / Live Wall no fallen al alternar PC y nube."

Write-Host ""
Write-Host "Esquema Neon alineado con modelos:" -ForegroundColor Cyan
Write-Host "  .\scripts\init_neon_desde_local.ps1"
Write-Host "  (Render ya corre: python init_db.py en pre-deploy)"

if ($RunInitDb) {
    Write-Host ""
    Write-Host "Ejecutando init_neon_desde_local.ps1 ..." -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot "init_neon_desde_local.ps1") -RutaRaiz $RutaRaiz
}

Write-Host ""
