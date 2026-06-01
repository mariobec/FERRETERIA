<#
.SYNOPSIS
  Instalador completo DEV -> máquina tienda: código (commit git) + dump Postgres + config.

.EXAMPLE
  .\scripts\crear_instalador_tienda_completo.ps1
  .\scripts\crear_instalador_tienda_completo.ps1 -Dest D:\USB\LhexIA_Instalador_Tienda
#>
[CmdletBinding()]
param(
    [string] $Dest = "",
    [switch] $SinDump
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$packName = "instalador_tienda_$stamp"

if ($Dest) {
    try { $packRoot = (Resolve-Path -LiteralPath $Dest).Path } catch { $packRoot = $Dest }
} else {
    $packRoot = Join-Path $repo "respaldos\$packName"
}

@(
    "$packRoot\01_BASE_DATOS",
    "$packRoot\02_CONFIG",
    "$packRoot\03_INSTRUCCIONES",
    "$packRoot\04_CODIGO\patch"
) | ForEach-Object { New-Item -ItemType Directory -Force -Path $_ | Out-Null }

Set-Location $repo
Write-Host "Generando instalador: $packRoot" -ForegroundColor Cyan

$commit = ((git -C $repo rev-parse HEAD) | Out-String).Trim()
$commitMsg = ((git -C $repo log -1 --format='%s') | Out-String).Trim()
$branch = ((git -C $repo rev-parse --abbrev-ref HEAD) | Out-String).Trim()
$dirty = git -C $repo status --porcelain
$isDirty = [bool]$dirty

$dumpFile = $null
if (-not $SinDump) {
    Write-Host 'Dump Postgres (DATABASE_URL en .env.local)...' -ForegroundColor Yellow
    python scripts/backup_neon_dump.py --url-key DATABASE_URL --out-dir "$packRoot\01_BASE_DATOS"
    if ($LASTEXITCODE -ne 0) { throw 'backup_neon_dump fallo' }
    $dump = Get-ChildItem "$packRoot\01_BASE_DATOS\neon_*.dump" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $dump) { throw 'No se genero el .dump' }
    $dumpFile = "piloto_sd_ferreteria_$stamp.dump"
    Rename-Item -LiteralPath $dump.FullName -NewName $dumpFile -Force

    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    if (Test-Path "$repo\.venv\Scripts\python.exe") {
        & "$repo\.venv\Scripts\python.exe" scripts\_check_maestra_erp.py *> "$packRoot\01_BASE_DATOS\erp_stats.txt"
    } else {
        python scripts\_check_maestra_erp.py *> "$packRoot\01_BASE_DATOS\erp_stats.txt"
    }
    $ErrorActionPreference = $prevEap
}

if (Test-Path "$repo\.env.local") {
    Copy-Item "$repo\.env.local" "$packRoot\02_CONFIG\.env.local.template" -Force
}
Copy-Item "$repo\.env.example" "$packRoot\02_CONFIG\.env.example" -Force

# Patch: cambios sin commit (excluye respaldos, docs pesados, .venv)
if ($isDirty) {
    Write-Host 'AVISO: working tree sucio — copiando patch a 04_CODIGO/patch/' -ForegroundColor Yellow
    foreach ($line in $dirty) {
        if ($line -match '^\?\?\s+(.+)$') { $rel = $Matches[1].Trim('"') }
        elseif ($line -match '^..?\s+(.+)$') { $rel = $Matches[1].Trim('"') }
        else { continue }
        $relNorm = $rel -replace '\\', '/'
        if ($relNorm -match '^(respaldos/|\.venv/|docs/Entrenamiento/|docs/Maestro Materiales/)') { continue }
        $src = Join-Path $repo $rel
        if (-not (Test-Path -LiteralPath $src)) { continue }
        if (Test-Path -LiteralPath $src -PathType Container) { continue }
        $dst = Join-Path "$packRoot\04_CODIGO\patch" $rel
        New-Item -ItemType Directory -Force -Path (Split-Path $dst -Parent) | Out-Null
        Copy-Item -LiteralPath $src -Destination $dst -Force
    }
}

git -C $repo log -5 --oneline | Out-File "$packRoot\03_INSTRUCCIONES\GIT_LOG.txt" -Encoding utf8
@"
commit=$commit
branch=$branch
message=$commitMsg
remote=https://github.com/mariobec/FERRETERIA.git
generated=$stamp
working_tree_dirty=$isDirty
"@ | Set-Content "$packRoot\03_INSTRUCCIONES\GIT_COMMIT.txt" -Encoding UTF8

Copy-Item "$repo\scripts\restaurar_piloto_tienda.bat" "$packRoot\03_INSTRUCCIONES\" -Force

$instBat = @'
@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

REM Instalador completo LhexIA tienda — codigo + datos
REM Copie esta carpeta a C:\LhexIA\_piloto\instalador_tienda_YYYYMMDD_HHMMSS
REM Repo destino: C:\LhexIA\ERP\sistema_ventas_limpio  (o C:\LhexIA\ERP)

set "PACK=%~dp0"
set "PACK=%PACK:~0,-1%"
set "REPO=C:\LhexIA\ERP\sistema_ventas_limpio"
if not exist "%REPO%\app.py" set "REPO=C:\LhexIA\ERP"
if not exist "%REPO%\app.py" (
  echo ERROR: No encuentro app.py en %REPO%
  echo Clone el repo: git clone https://github.com/mariobec/FERRETERIA.git "%REPO%"
  pause & exit /b 1
)

for /f "tokens=1,* delims==" %%A in ('findstr /B "commit=" "%PACK%\03_INSTRUCCIONES\GIT_COMMIT.txt"') do set "GIT_COMMIT=%%B"
echo Pack: %PACK%
echo Repo: %REPO%
echo Commit objetivo: %GIT_COMMIT%
echo.

cd /d "%REPO%"

echo [1/6] Git fetch + checkout commit del instalador...
git fetch origin
if errorlevel 1 ( echo AVISO: git fetch fallo — revise red & exit /b 1 )
git checkout %GIT_COMMIT%
if errorlevel 1 (
  echo ERROR: checkout fallo. Ejecute: git fetch origin ^&^& git checkout %GIT_COMMIT%
  pause & exit /b 1
)

if exist "%PACK%\04_CODIGO\patch" (
  echo [2/6] Aplicando patch sin commit...
  xcopy /E /Y /I "%PACK%\04_CODIGO\patch\*" "%REPO%\"
) else (
  echo [2/6] Sin patch adicional
)

echo [3/6] Python .venv...
if exist ".venv\Scripts\python.exe" rmdir /s /q .venv
python -m venv .venv
if errorlevel 1 ( echo ERROR: python -m venv & pause & exit /b 1 )
".venv\Scripts\python.exe" -m pip install -r requirements.txt -q

echo [4/6] Restaurar base ferreteria_local...
set "DUMP="
for %%F in ("%PACK%\01_BASE_DATOS\piloto_sd_ferreteria_*.dump") do set "DUMP=%%F"
if not defined DUMP for %%F in ("%PACK%\01_BASE_DATOS\*.dump") do set "DUMP=%%F"
if not defined DUMP (
  echo ERROR: falta .dump en 01_BASE_DATOS
  pause & exit /b 1
)
call "%PACK%\03_INSTRUCCIONES\restaurar_piloto_tienda.bat" "!DUMP!"

echo [5/6] Config .env.local...
if exist "%PACK%\02_CONFIG\.env.local.template" (
  copy /Y "%PACK%\02_CONFIG\.env.local.template" "%REPO%\.env.local" >nul
  echo Copiado .env.local — ajuste DATABASE_URL localhost y PUBLIC_SITE_URL LAN
) else (
  echo AVISO: copie manualmente 02_CONFIG\.env.local.template
)

echo [6/6] Verificacion rapida...
".venv\Scripts\python.exe" -c "import app; print('import app OK')" 2>nul
if errorlevel 1 echo AVISO: import app fallo — revise dependencias

echo.
echo === Instalacion completa ===
echo Arrancar: %REPO%\arrancar_erp.bat
echo URL: http://localhost:5000
echo Smoke: caja SLA, POS, vitrina
pause
'@
Set-Content -Path "$packRoot\03_INSTRUCCIONES\instalar_tienda_completo.bat" -Value $instBat -Encoding ASCII

$leeme = @"
LhexIA — instalador completo tienda ($stamp)
============================================

Contenido:
  01_BASE_DATOS/   dump Postgres + erp_stats.txt
  02_CONFIG/       .env.local.template + .env.example
  03_INSTRUCCIONES/instalar_tienda_completo.bat  ← EJECUTAR EN TIENDA
  04_CODIGO/patch/ cambios sin commit (si los hubo en DEV)

Git objetivo:
  commit: $commit
  branch: $branch
  msg:    $commitMsg

Pasos en máquina tienda
-----------------------
1. Copiar esta carpeta a:
   C:\LhexIA\_piloto\$packName
2. Asegurar repo clonado:
   C:\LhexIA\ERP\sistema_ventas_limpio
   (git clone https://github.com/mariobec/FERRETERIA.git)
3. Ejecutar como usuario normal:
   C:\LhexIA\_piloto\$packName\03_INSTRUCCIONES\instalar_tienda_completo.bat
4. Editar .env.local: DATABASE_URL local + PUBLIC_SITE_URL LAN
5. arrancar_erp.bat

IMPORTANTE piloto sin pinturas en piso:
  No activar VITRINA_FABRICA_COLOR_PREVIEW=1
  Si BuildError modulo pinturas: omitir boton en caja o registrar blueprint opcional

Backup diario tienda:
  pg_dump -Fc -h localhost -U postgres -d ferreteria_local -f respaldos\backup_YYYYMMDD.dump
"@
Set-Content -Path "$packRoot\LEEME_INSTALADOR.txt" -Value $leeme -Encoding UTF8

$sum = (Get-ChildItem $packRoot -Recurse -File | Measure-Object -Property Length -Sum).Sum
Write-Host "Listo: $packRoot ($([math]::Round($sum/1MB,2)) MB)" -ForegroundColor Green
Write-Host "Ejecutar en tienda: $packRoot\03_INSTRUCCIONES\instalar_tienda_completo.bat" -ForegroundColor Green
