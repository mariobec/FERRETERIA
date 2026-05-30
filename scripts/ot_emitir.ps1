<#
.SYNOPSIS
  Emite Orden de Transporte (OT) SAP-style: DEV -> QAS (SAMBOX) o QAS -> PRD.

.EXAMPLE
  .\scripts\ot_emitir.ps1 -Destino qas -Descripcion "Vitrina logo SD + Red Chilemat"
  .\scripts\ot_emitir.ps1 -Destino prd -OtQasRef "OT-20260529-125912-dev-qas"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('qas', 'prd')]
    [string] $Destino,

    [string] $Descripcion = "",
    [string] $OtQasRef = "",
    [switch] $SinDump
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $repo

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$otId = "OT-$stamp-$Destino"
$otRoot = Join-Path $repo "respaldos\transporte\$otId"
$dirCodigo = Join-Path $otRoot '01_CODIGO'
$dirPatch = Join-Path $dirCodigo 'patch'
$dirDatos = Join-Path $otRoot '02_DATOS'
$dirInst = Join-Path $otRoot '03_INSTRUCCIONES'

@($dirCodigo, $dirPatch, $dirDatos, $dirInst) | ForEach-Object { New-Item -ItemType Directory -Force -Path $_ | Out-Null }

Write-Host "Emitiendo $otId -> $Destino" -ForegroundColor Cyan

$commit = ((git -C $repo log -1 --format='%H') | Out-String).Trim()
$commitMsg = ((git -C $repo log -1 --format='%s') | Out-String).Trim()
$branch = ((git -C $repo rev-parse --abbrev-ref HEAD) | Out-String).Trim()
$dirty = git -C $repo status --porcelain
$isDirty = [bool]$dirty

git -C $repo diff --name-only HEAD | Out-File (Join-Path $dirCodigo 'archivos_modificados.txt') -Encoding utf8
git -C $repo status --porcelain | Out-File (Join-Path $dirCodigo 'git_status_porcelain.txt') -Encoding utf8
git -C $repo log -5 --oneline | Out-File (Join-Path $dirCodigo 'GIT_LOG.txt') -Encoding utf8
git -C $repo tag --list 'checkpoint/*' | Out-File (Join-Path $dirCodigo 'GIT_TAGS.txt') -Encoding utf8

if ($isDirty) {
    Write-Host 'AVISO: working tree con cambios sin commit - se copian a 01_CODIGO/patch/' -ForegroundColor Yellow
    foreach ($line in $dirty) {
        if ($line -match '^\?\?\s+(.+)$') {
            $rel = $Matches[1].Trim('"')
        } elseif ($line -match '^..?\s+(.+)$') {
            $rel = $Matches[1].Trim('"')
        } else { continue }
        $relNorm = $rel -replace '\\', '/'
        if ($relNorm -match '^(respaldos/|docs/|\.venv/)') { continue }
        $src = Join-Path $repo $rel
        if (-not (Test-Path -LiteralPath $src)) { continue }
        if (Test-Path -LiteralPath $src -PathType Container) { continue }
        $dst = Join-Path $dirPatch $rel
        $dstDir = Split-Path $dst -Parent
        New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
        Copy-Item -LiteralPath $src -Destination $dst -Force
    }
}

$tagName = "checkpoint/ot-$Destino-$stamp"
$prevEapTag = $ErrorActionPreference
$ErrorActionPreference = 'SilentlyContinue'
git -C $repo tag -a $tagName -m "OT $otId - $Descripcion" 2>$null | Out-Null
$ErrorActionPreference = $prevEapTag
if ($LASTEXITCODE -ne 0) {
    $tagName = $null
    Write-Host 'Tag no creado (configure git user o working tree sucio).' -ForegroundColor Yellow
}

$dumpFile = $null
$statsFile = $null
if ($Destino -eq 'qas' -and -not $SinDump) {
    Write-Host 'Dump Postgres DEV (ferreteria_local)...' -ForegroundColor Yellow
    python scripts/backup_neon_dump.py --url-key DATABASE_URL --out-dir $dirDatos
    if ($LASTEXITCODE -ne 0) { throw 'backup_neon_dump fallo' }
    $dump = Get-ChildItem (Join-Path $dirDatos 'neon_*.dump') | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($dump) {
        $dumpFile = "piloto_sd_ferreteria_$stamp.dump"
        Rename-Item -LiteralPath $dump.FullName -NewName $dumpFile -Force
    }
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    if (Test-Path "$repo\.venv\Scripts\python.exe") {
        & (Join-Path $repo '.venv\Scripts\python.exe') scripts\_check_maestra_erp.py *> (Join-Path $dirDatos 'erp_stats.txt')
    } else {
        python scripts\_check_maestra_erp.py *> (Join-Path $dirDatos 'erp_stats.txt')
    }
    $ErrorActionPreference = $prevEap
    $statsFile = 'erp_stats.txt'
}

if ($Destino -eq 'prd') {
    $planPrd = "# Plan datos PRD (Neon) - ejecutar tras sign-off QAS`n`n"
    $planPrd += "## Maestro pendiente`n"
    $planPrd += "python scripts/maestra_activar_cm_compras.py --confirm-neon`n"
    $planPrd += "python scripts/maestra_completar_catalogo_sd.py --confirm-neon`n"
    $planPrd += "python scripts/_check_maestra_erp.py`n`n"
    $planPrd += "## Sync local a Neon (solo si QAS valido)`n"
    $planPrd += "python scripts/sync_local_neon_render.py --verify-only`n"
    $planPrd += "python scripts/sync_local_neon_render.py`n`n"
    $planPrd += "## Backup antes de import`n"
    $planPrd += "python scripts/backup_neon_dump.py`n"
    Set-Content (Join-Path $dirDatos 'PLAN_DATOS_PRD.md') -Value $planPrd -Encoding UTF8
}

$estado = if ($Destino -eq 'qas') { 'LIBERADA' } else { 'PENDIENTE_SIGNOFF_QAS' }

$orden = [ordered]@{
    ot_id           = $otId
    tipo            = if ($Destino -eq 'qas') { 'OT-DEV-QAS' } else { 'OT-QAS-PRD' }
    descripcion     = $Descripcion
    estado          = $estado
    origen          = 'DEV'
    destino         = if ($Destino -eq 'qas') { 'QAS (SAMBOX)' } else { 'PRD (Neon/Render)' }
    emitido_en      = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
    emitido_por     = $env:USERNAME
    git_commit      = $commit
    git_commit_msg  = $commitMsg
    git_branch      = $branch
    git_tag         = $tagName
    working_tree_dirty = $isDirty
    ot_qas_referencia = $OtQasRef
    codigo          = @{
        incluye_patch = $isDirty
        patch_dir     = if ($isDirty) { '01_CODIGO/patch' } else { $null }
    }
    datos           = @{
        dump          = $dumpFile
        erp_stats     = $statsFile
        plan_prd      = if ($Destino -eq 'prd') { '02_DATOS/PLAN_DATOS_PRD.md' } else { $null }
    }
    prerequisitos_prd = if ($Destino -eq 'prd') {
        @(
            'Sign-off UAT en SAMBOX (QAS)',
            'OT-DEV-QAS importada y validada',
            'Backup Neon antes de sync'
        )
    } else { @() }
}

$orden | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $otRoot 'orden.json') -Encoding UTF8

if (Test-Path (Join-Path $repo '.env.example')) {
    Copy-Item (Join-Path $repo '.env.example') (Join-Path $dirDatos '.env.example') -Force
}
if ($Destino -eq 'qas' -and (Test-Path (Join-Path $repo '.env.local'))) {
    Copy-Item (Join-Path $repo '.env.local') (Join-Path $dirDatos '.env.local.template') -Force
}

Copy-Item (Join-Path $repo 'scripts\restaurar_piloto_tienda.bat') $dirInst -Force -ErrorAction SilentlyContinue
Copy-Item (Join-Path $repo 'scripts\instalar_piloto_tienda_user.bat') $dirInst -Force -ErrorAction SilentlyContinue

if ($Destino -eq 'qas') {
    $importQas = @()
    $importQas += '# IMPORT OT en SAMBOX (QAS)'
    $importQas += ''
    $importQas += 'Ruta repo QAS: C:\LhexIA\ERP\sistema_ventas_limpio'
    $importQas += "Staging OT:   C:\LhexIA\respaldos\transporte\$otId"
    $importQas += ''
    $importQas += '## 1. Copiar OT'
    $importQas += "Origen: $otRoot"
    $importQas += "Destino SAMBOX: C:\LhexIA\respaldos\transporte\$otId"
    $importQas += ''
    $importQas += '## 2. Codigo (OT-Codigo)'
    $importQas += 'cd C:\LhexIA\ERP\sistema_ventas_limpio'
    $importQas += 'git fetch origin'
    $importQas += "git checkout $commit"
    if ($tagName) { $importQas += "git checkout tags/$tagName" }
    if ($isDirty) {
        $importQas += "xcopy /E /Y C:\LhexIA\respaldos\transporte\$otId\01_CODIGO\patch\* ."
    }
    $importQas += ''
    $importQas += '## 3. Entorno Python (NO copiar .venv)'
    $importQas += 'rmdir /s /q .venv'
    $importQas += 'python -m venv .venv'
    $importQas += '.venv\Scripts\python.exe -m pip install -r requirements.txt'
    $importQas += ''
    $importQas += '## 4. Datos (OT-Datos)'
    $importQas += 'createdb -U postgres ferreteria_local'
    $importQas += "restaurar_piloto_tienda.bat `"C:\LhexIA\respaldos\transporte\$otId\02_DATOS\$dumpFile`""
    $importQas += ''
    $importQas += '## 5. Config'
    $importQas += 'Copiar 02_DATOS\.env.local.template a .env.local'
    $importQas += 'Ajustar DATABASE_URL local y PUBLIC_SITE_URL=http://IP-LAN:5000'
    $importQas += ''
    $importQas += '## 6. Validacion UAT'
    $importQas += 'arrancar_erp.bat'
    $importQas += 'Probar POS, vitrina Chilemat, inventario enrolamiento'
    $importQas += ''
    $importQas += '## 7. Sign-off'
    $importQas += 'Completar SIGNOFF_QAS.txt antes de importar OT-PRD'
    $importQas | Set-Content (Join-Path $dirInst 'IMPORT_QAS.md') -Encoding UTF8

    $signoff = @()
    $signoff += "SIGN-OFF QAS (SAMBOX) - $otId"
    $signoff += '================================'
    $signoff += 'Fecha UAT: ___________'
    $signoff += 'Validado por: ___________'
    $signoff += ''
    $signoff += '[ ] ERP arranca sin errores'
    $signoff += '[ ] Login admin OK'
    $signoff += '[ ] POS emite vale / cobro'
    $signoff += '[ ] Vitrina catalogo + logo Chilemat'
    $signoff += '[ ] Stock tienda/bodega coherente'
    $signoff += '[ ] Ollama no bloquea ERP'
    $signoff += ''
    $signoff += 'Observaciones:'
    $signoff += '_________________________________'
    $signoff += ''
    $signoff += 'APROBADO PARA PRD:  SI / NO'
    $signoff += 'Firma: ___________'
    $signoff | Set-Content (Join-Path $dirInst 'SIGNOFF_QAS.txt') -Encoding UTF8

    $bat = @()
    $bat += '@echo off'
    $bat += 'chcp 65001 >nul'
    $bat += 'setlocal'
    $bat += "set `"OT=C:\LhexIA\respaldos\transporte\$otId`""
    $bat += 'set "REPO=C:\LhexIA\ERP\sistema_ventas_limpio"'
    $bat += 'echo OT: %OT%'
    $bat += 'echo Repo: %REPO%'
    $bat += 'if not exist "%OT%\orden.json" ('
    $bat += '  echo ERROR: No existe la OT en %OT%'
    $bat += '  pause & exit /b 1'
    $bat += ')'
    $bat += 'cd /d "%REPO%"'
    $bat += 'echo.'
    $bat += "echo [1/4] Git checkout $commit"
    $bat += "git checkout $commit"
    $bat += 'if exist "%OT%\01_CODIGO\patch" ('
    $bat += '  echo [2/4] Aplicando patch codigo...'
    $bat += '  xcopy /E /Y /I "%OT%\01_CODIGO\patch\*" "%REPO%\"'
    $bat += ')'
    $bat += 'echo [3/4] Restaurar dump...'
    $bat += "call `"%OT%\03_INSTRUCCIONES\restaurar_piloto_tienda.bat`" `"%OT%\02_DATOS\$dumpFile`""
    $bat += 'echo [4/4] Revise .env.local y ejecute arrancar_erp.bat'
    $bat += 'pause'
    $bat | Set-Content (Join-Path $dirInst 'importar_ot_qas.bat') -Encoding ASCII
}

if ($Destino -eq 'prd') {
    $importPrd = @()
    $importPrd += '# IMPORT OT en PRD (Neon + Render)'
    $importPrd += ''
    $importPrd += 'NO ejecutar sin SIGNOFF_QAS.txt de la OT QAS correspondiente.'
    $importPrd += ''
    $importPrd += "OT QAS referencia: $OtQasRef"
    $importPrd += "Commit codigo: $commit"
    $importPrd += "Tag: $tagName"
    $importPrd += ''
    $importPrd += '## 1. Codigo -> Render'
    $importPrd += "git push origin $commit"
    $importPrd += ''
    $importPrd += '## 2. Datos -> Neon'
    $importPrd += 'Ver 02_DATOS/PLAN_DATOS_PRD.md'
    $importPrd += 'Opcion B: sync_local_neon_render.py tras backup Neon'
    $importPrd += ''
    $importPrd += '## 3. Verificacion PRD'
    $importPrd += 'python scripts/_check_maestra_erp.py'
    $importPrd += 'pytest tests/ -m smoke -q'
    $importPrd += ''
    $importPrd += '## 4. Cierre OT'
    $importPrd += 'Actualizar orden.json estado -> IMPORTADA_PRD'
    $importPrd | Set-Content (Join-Path $dirInst 'IMPORT_PRD.md') -Encoding UTF8
}

$leeme = @()
$leeme += "LhexIA - Orden de Transporte $otId"
$leeme += '=================================='
if ($Destino -eq 'qas') { $leeme += 'Destino: QAS (SAMBOX)' } else { $leeme += 'Destino: PRD (Neon/Render)' }
$leeme += "Estado:  $estado"
$leeme += "Commit:  $commit"
if ($tagName) { $leeme += "Tag:     $tagName" }
if ($isDirty) { $leeme += 'AVISO: incluye patch sin commit en 01_CODIGO/patch/' }
$leeme += ''
$leeme += 'Ver orden.json y 03_INSTRUCCIONES/'
$leeme | Set-Content (Join-Path $otRoot 'LEEME_OT.txt') -Encoding UTF8

$sum = (Get-ChildItem $otRoot -Recurse -File | Measure-Object -Property Length -Sum).Sum
$sumMb = [math]::Round(($sum / 1MB), 2)
Write-Host ('OT emitida: ' + $otRoot + ' (' + $sumMb + ' MB)') -ForegroundColor Green
Write-Host ('Manifiesto: ' + (Join-Path $otRoot 'orden.json')) -ForegroundColor Green
