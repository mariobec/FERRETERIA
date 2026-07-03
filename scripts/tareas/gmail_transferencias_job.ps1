# Job Gmail transferencias banco — sin ventana (tarea programada Windows)
$ErrorActionPreference = 'Continue'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Py = Join-Path $RepoRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path $Py)) { $Py = Join-Path $RepoRoot '.venv\Scripts\python.exe' }
if (-not (Test-Path $Py)) { $Py = Join-Path $RepoRoot 'venv\Scripts\pythonw.exe' }
if (-not (Test-Path $Py)) { $Py = Join-Path $RepoRoot 'venv\Scripts\python.exe' }

$LogDir = Join-Path $RepoRoot 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir ("gmail_transferencias_job_{0:yyyy-MM-dd}.log" -f (Get-Date))

function Write-JobLog([string]$Message) {
    $line = "{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $Message
    Add-Content -Path $Log -Value $line -Encoding UTF8
}

Write-JobLog "=== gmail_transferencias_job (hidden) ==="
Write-JobLog "Carpeta ERP: $RepoRoot"

if (-not (Test-Path $Py)) {
    Write-JobLog "ERROR: no existe python venv: $Py"
    exit 1
}
if (-not (Test-Path (Join-Path $RepoRoot '.env.local'))) {
    Write-JobLog "AVISO: falta .env.local"
    exit 1
}

Push-Location $RepoRoot
try {
    & $Py scripts\setup_gmail_transferencias_correo.py --solo-etiquetar --limite 60 --dias 7 *>> $Log
    $err1 = $LASTEXITCODE

    & $Py scripts\lector_correo_transferencias.py --limite 60 *>> $Log
    $err2 = $LASTEXITCODE

    Write-JobLog "Fin job ERR etiquetar=$err1 sync=$err2"
    if ($err1 -ge 2) { exit $err1 }
    if ($err2 -ge 2) { exit $err2 }
    exit 0
} finally {
    Pop-Location
}
