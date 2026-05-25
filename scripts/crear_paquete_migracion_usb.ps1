<#
.SYNOPSIS
  Arma en el USB la carpeta LhexIA_Migracion_SD_* (BD, config, CSV, checklist).

.PARAMETER UsbDrive
  Letra de unidad USB, ej. E

.EXAMPLE
  .\scripts\crear_paquete_migracion_usb.ps1 -UsbDrive E
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $UsbDrive
)

$ErrorActionPreference = 'Stop'
$UsbDrive = $UsbDrive.TrimEnd(':').TrimEnd('\')
$stamp = Get-Date -Format 'yyyyMMdd'
$usbRoot = "${UsbDrive}:\LhexIA_Migracion_SD_$stamp"
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

@(
    "$usbRoot\01_BASE_DATOS",
    "$usbRoot\02_CONFIG",
    "$usbRoot\03_CARGA_DATOS",
    "$usbRoot\04_DOCUMENTACION",
    "$usbRoot\05_REPO_INSTRUCCIONES"
) | ForEach-Object { New-Item -ItemType Directory -Force -Path $_ | Out-Null }

Write-Host "USB: $usbRoot" -ForegroundColor Cyan
Set-Location $repo

Write-Host 'Dump Neon...' -ForegroundColor Yellow
python scripts/backup_neon_dump.py --out-dir "$usbRoot\01_BASE_DATOS"
if ($LASTEXITCODE -ne 0) { throw 'backup_neon_dump falló' }

Write-Host 'Dump Postgres local (si DATABASE_URL es local)...' -ForegroundColor Yellow
python scripts/backup_neon_dump.py --url-key DATABASE_URL --out-dir "$usbRoot\01_BASE_DATOS"
$localDump = Get-ChildItem "$usbRoot\01_BASE_DATOS\neon_*.dump" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($localDump -and $localDump.Name -match '^neon_') {
    $newName = $localDump.Name -replace '^neon_', 'local_ferreteria_'
    Rename-Item -LiteralPath $localDump.FullName -NewName $newName -Force
}

Write-Host 'verify-only...' -ForegroundColor Yellow
python scripts/sync_local_neon_render.py --verify-only 2>&1 |
    Out-File "$usbRoot\01_BASE_DATOS\verify_local_vs_neon.txt" -Encoding utf8

Copy-Item "$repo\.env.local" "$usbRoot\02_CONFIG\.env.local" -Force -ErrorAction SilentlyContinue
if (Test-Path "$repo\.env") { Copy-Item "$repo\.env" "$usbRoot\02_CONFIG\.env" -Force }
Copy-Item "$repo\.env.example" "$usbRoot\02_CONFIG\.env.example" -Force
Copy-Item "$repo\scripts\CHECKLIST_MIGRACION_PC.md" "$usbRoot\04_DOCUMENTACION\" -Force
if (Test-Path "$repo\CARGA DE DATOS") {
    Copy-Item "$repo\CARGA DE DATOS" "$usbRoot\03_CARGA_DATOS\CARGA_DE_DATOS" -Recurse -Force
}
if (Test-Path "$repo\datos_rcv") {
    Copy-Item "$repo\datos_rcv" "$usbRoot\03_CARGA_DATOS\datos_rcv" -Recurse -Force
}

git -C $repo log -1 --oneline | Out-File "$usbRoot\05_REPO_INSTRUCCIONES\GIT_ULTIMO_COMMIT.txt" -Encoding utf8
git -C $repo remote -v | Out-File "$usbRoot\05_REPO_INSTRUCCIONES\GIT_REMOTO.txt" -Encoding utf8 -Append

$readme = @"
LhexIA — paquete migración ($stamp)
==================================

01_BASE_DATOS
  neon_*.dump          → Restaurar en Postgres PC nuevo (verdad en nube Neon)
  local_ferreteria_* → Copia Postgres de esta PC (comparar con neon)
  verify_local_vs_neon.txt → ¿Local = Neon?

02_CONFIG
  .env.local — SECRETO; pegar en raíz del repo en PC nuevo

03_CARGA_DATOS — CSV y RCV

04_DOCUMENTACION — CHECKLIST_MIGRACION_PC.md

05_REPO_INSTRUCCIONES
  git clone https://github.com/mariobec/FERRETERIA.git

PC nuevo:
  pg_restore ... neon_*.dump
  Ajustar DATABASE_URL en .env.local
  python scripts/sync_local_neon_render.py --verify-only
"@
Set-Content -Path "$usbRoot\LEEME_MIGRACION.txt" -Value $readme -Encoding UTF8

$sum = (Get-ChildItem $usbRoot -Recurse -File | Measure-Object -Property Length -Sum).Sum
Write-Host "Listo: $usbRoot ($([math]::Round($sum/1MB,2)) MB)" -ForegroundColor Green
