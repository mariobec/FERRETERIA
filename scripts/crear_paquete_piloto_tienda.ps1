<#
.SYNOPSIS
  Paquete piloto SD: dump ferreteria_local + config + instrucciones para máquina de tienda.

.EXAMPLE
  .\scripts\crear_paquete_piloto_tienda.ps1
  .\scripts\crear_paquete_piloto_tienda.ps1 -Dest D:\USB\LhexIA_Piloto_SD
#>
[CmdletBinding()]
param(
    [string] $Dest = ""
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
if ($Dest) {
    try {
        $packRoot = (Resolve-Path -LiteralPath $Dest).Path
    } catch {
        $packRoot = $Dest
    }
} else {
    $packRoot = Join-Path $repo "respaldos\piloto_tienda_$stamp"
}

@(
    "$packRoot\01_BASE_DATOS",
    "$packRoot\02_CONFIG",
    "$packRoot\03_INSTRUCCIONES"
) | ForEach-Object { New-Item -ItemType Directory -Force -Path $_ | Out-Null }

Set-Location $repo
Write-Host "Paquete: $packRoot" -ForegroundColor Cyan

Write-Host 'Dump Postgres local (ferreteria_local)...' -ForegroundColor Yellow
python scripts/backup_neon_dump.py --url-key DATABASE_URL --out-dir "$packRoot\01_BASE_DATOS"
if ($LASTEXITCODE -ne 0) { throw 'backup falló' }

$dump = Get-ChildItem "$packRoot\01_BASE_DATOS\neon_*.dump" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $dump) { throw 'No se generó el .dump' }
$targetName = "piloto_sd_ferreteria_$stamp.dump"
Rename-Item -LiteralPath $dump.FullName -NewName $targetName -Force

Write-Host 'Estadísticas ERP local...' -ForegroundColor Yellow
$prevEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& .\.venv\Scripts\python.exe scripts\_check_maestra_erp.py *> "$packRoot\01_BASE_DATOS\erp_stats.txt"
$ErrorActionPreference = $prevEap

if (Test-Path "$repo\.env.local") {
    Copy-Item "$repo\.env.local" "$packRoot\02_CONFIG\.env.local" -Force
}
Copy-Item "$repo\.env.example" "$packRoot\02_CONFIG\.env.example" -Force

git -C $repo log -1 --format="%H %s" | Out-File "$packRoot\03_INSTRUCCIONES\GIT_COMMIT.txt" -Encoding utf8
git -C $repo tag --list "checkpoint/piloto-sd-*" | Out-File "$packRoot\03_INSTRUCCIONES\GIT_TAGS.txt" -Encoding utf8 -Append
Copy-Item "$repo\scripts\restaurar_piloto_tienda.bat" "$packRoot\03_INSTRUCCIONES\" -Force

$readme = @"
LhexIA — paquete piloto tienda Santo Domingo ($stamp)
=====================================================

Origen: PC desarrollo (ferreteria_local + maestro completo).
NO usar Neon en operación diaria — Postgres local en la máquina de tienda.

01_BASE_DATOS
  piloto_sd_ferreteria_$stamp.dump  → Restaurar en Postgres tienda
  erp_stats.txt                     → Conteos productos/puentes

02_CONFIG
  .env.local — Copiar a raíz del repo en tienda
  Ajustar en tienda:
    DATABASE_URL=postgresql://postgres:CLAVE@localhost:5432/ferreteria_local
    PUBLIC_SITE_URL=http://IP-LAN-TIENDA:5000   (ej. http://192.168.1.50:5000)
  NO apuntar DATABASE_URL a neon.tech en piso.

03_INSTRUCCIONES
  restaurar_piloto_tienda.bat
  GIT_COMMIT.txt — checkout este commit en tienda

Pasos en máquina de tienda
--------------------------
1. git fetch && git checkout $(Get-Content "$packRoot\03_INSTRUCCIONES\GIT_COMMIT.txt" -ErrorAction SilentlyContinue)
   (o git pull origin main si ya está en el commit del paquete)
2. .venv + pip install -r requirements.txt
3. Crear BD vacía si no existe: createdb -U postgres ferreteria_local
4. Ejecutar restaurar_piloto_tienda.bat (ruta al .dump)
5. Copiar 02_CONFIG\.env.local → raíz repo (revisar clave postgres)
6. arrancar_erp.bat → probar http://localhost:5000
7. Otras PCs: http://IP-LAN:5000

Backup diario en tienda:
  pg_dump -Fc -h localhost -U postgres -d ferreteria_local -f respaldos\backup_YYYYMMDD.dump
"@
Set-Content -Path "$packRoot\LEEME_PILOTO.txt" -Value $readme -Encoding UTF8

$sum = (Get-ChildItem $packRoot -Recurse -File | Measure-Object -Property Length -Sum).Sum
Write-Host "Listo: $packRoot ($([math]::Round($sum/1MB,2)) MB)" -ForegroundColor Green
Write-Host "Dump: $packRoot\01_BASE_DATOS\$targetName" -ForegroundColor Green
