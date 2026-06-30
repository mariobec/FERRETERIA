# LhexIA ERP — arranque automatico (exe PyInstaller o .venv legacy)
$ErrorActionPreference = 'Continue'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Exe = Join-Path $RepoRoot 'LhexIA_ERP.exe'
$Py = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$LogDir = Join-Path $RepoRoot 'logs'
$LogFile = Join-Path $LogDir 'servidor_erp_autostart.log'

if ($env:LHEXIA_PG_WAIT_SEC) { $PgWaitSec = [int]$env:LHEXIA_PG_WAIT_SEC } else { $PgWaitSec = 180 }
if ($env:LHEXIA_RESTART_DELAY_SEC) { $restartDelay = [int]$env:LHEXIA_RESTART_DELAY_SEC } else { $restartDelay = 45 }
if ($env:LHEXIA_MAX_RESTARTS) { $maxRestarts = [int]$env:LHEXIA_MAX_RESTARTS } else { $maxRestarts = 9999 }
$PgPollSec = 5

function Write-ErpLog {
    param([string]$Message)
    $line = '{0:yyyy-MM-dd HH:mm:ss} {1}' -f (Get-Date), $Message
    if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

function Test-PortListening {
    param([int]$Port)
    try {
        $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        return [bool]$c
    } catch { return $false }
}

function Wait-PostgresReady {
    $deadline = (Get-Date).AddSeconds($PgWaitSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $client = New-Object System.Net.Sockets.TcpClient
            $client.Connect('127.0.0.1', 5432)
            $client.Close()
            Write-ErpLog 'Postgres local listo (puerto 5432).'
            return $true
        } catch { Start-Sleep -Seconds $PgPollSec }
    }
    Write-ErpLog "AVISO: Postgres no respondio en ${PgWaitSec}s; se intenta arrancar Flask igual."
    return $false
}

Set-Location $RepoRoot

$useExe = Test-Path $Exe
if (-not $useExe -and -not (Test-Path $Py)) {
    Write-ErpLog "ERROR: No existe LhexIA_ERP.exe ni .venv"
    exit 1
}

if (Test-PortListening -Port 5000) {
    Write-ErpLog 'Servidor ya escuchando en puerto 5000; no se duplica.'
    exit 0
}

Wait-PostgresReady | Out-Null

$env:PGCLIENTENCODING = 'UTF8'
$env:FLASK_DEBUG = '0'
$env:FLASK_TEMPLATE_RELOAD = '0'
$env:LHEXIA_SKIP_VENV_BOOTSTRAP = '1'

Write-ErpLog "Iniciando LhexIA ERP en $RepoRoot ($(if ($useExe) {'exe'} else {'venv'}))..."

$attempt = 0
while ($attempt -lt $maxRestarts) {
    $attempt++
    if ($attempt -gt 1) {
        Write-ErpLog "Reintento $attempt tras caida (espera ${restartDelay}s)..."
        Start-Sleep -Seconds $restartDelay
        if (Test-PortListening -Port 5000) { exit 0 }
    }
    Write-ErpLog "Arranque intento $attempt — http://127.0.0.1:5000"
    try {
        if ($useExe) {
            & $Exe 2>&1 | ForEach-Object { Write-ErpLog $_.ToString() }
        } else {
            & $Py app.py 2>&1 | ForEach-Object { Write-ErpLog $_.ToString() }
        }
        $code = $LASTEXITCODE
    } catch {
        Write-ErpLog "ERROR al arrancar: $_"
        $code = 1
    }
    Write-ErpLog "Proceso termino con codigo $code."
    if ($code -eq 0) { break }
}
Write-ErpLog 'Fin del arranque automatico.'
exit 0
