<#
.SYNOPSIS
  Ejecuta init_db.py contra Neon usando credenciales de .env.local (sin subir secretos a git).

.DESCRIPTION
  Lee NEON_DATABASE_URL si existe; si no, usa DATABASE_URL. Solo tiene sentido si esa URL apunta a Neon
  (o a la misma Postgres que usás en Render).

  Uso típico antes o después de git push: alinear tablas/roles/admin con los modelos actuales.
  Render también corre init_db en pre-deploy; este script te permite adelantar o verificar en local.

.PARAMETER RutaRaiz
  Raíz del repo (donde está app.py). Por defecto: padre de scripts/.

.EXAMPLE
  .\scripts\init_neon_desde_local.ps1
#>
[CmdletBinding()]
param(
    [string] $RutaRaiz = ""
)

$ErrorActionPreference = "Stop"
if (-not $RutaRaiz) {
    $RutaRaiz = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}
Set-Location $RutaRaiz

$envFile = Join-Path $RutaRaiz ".env.local"
if (-not (Test-Path -LiteralPath $envFile)) {
    Write-Error "No existe .env.local en $RutaRaiz. Creá el archivo con NEON_DATABASE_URL o DATABASE_URL (Neon)."
}

function Get-EnvValueFromFile {
    param([string]$Path, [string]$Key)
    $pattern = "^\s*$([regex]::Escape($Key))\s*=\s*(.+)\s*$"
    foreach ($line in Get-Content -LiteralPath $Path -Encoding utf8) {
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

$url = (Get-EnvValueFromFile -Path $envFile -Key "NEON_DATABASE_URL").Trim()
if (-not $url) {
    $url = (Get-EnvValueFromFile -Path $envFile -Key "DATABASE_URL").Trim()
}
if (-not $url) {
    Write-Error "En .env.local definí NEON_DATABASE_URL (recomendado si local es Postgres distinto) o DATABASE_URL apuntando a Neon."
}

Write-Host "Usando init_db.py contra la URL configurada (no se imprime la cadena completa)."
if ($url -notmatch "postgres") {
    Write-Warning "La URL no parece Postgres; revisá .env.local."
}

$prev = $env:DATABASE_URL
try {
    $env:DATABASE_URL = $url
    python init_db.py
    if ($LASTEXITCODE -ne 0) {
        Write-Error "init_db.py terminó con código $LASTEXITCODE"
    }
}
finally {
    if ($null -ne $prev) { $env:DATABASE_URL = $prev } else { Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue }
}

Write-Host "Listo. Siguiente paso habitual: git push para que Render despliegue el mismo código."
