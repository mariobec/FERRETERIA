# LhexIA Operador — instalación Ollama en PC Santo Domingo (Windows)
# Ejecutar en PowerShell como usuario normal (no requiere admin salvo firewall).
# PC i3 16GB: usar -ModelLite (modelo 3B, más liviano).

param(
    [switch]$ModelLite
)

$ErrorActionPreference = "Stop"
if ($ModelLite) {
    $Model = "qwen2.5:3b-instruct-q4_K_M"
} else {
    $Model = "qwen2.5:7b-instruct-q4_K_M"
}

Write-Host "=== LhexIA Operador — setup Ollama ===" -ForegroundColor Cyan

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama no está en PATH. Descargue e instale desde https://ollama.com/download" -ForegroundColor Yellow
    Write-Host "Luego cierre y abra PowerShell y vuelva a ejecutar este script."
    exit 1
}

Write-Host "Descargando modelo $Model (puede tardar varios minutos)..."
ollama pull $Model

Write-Host "Verificando API local..."
try {
    $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 10
    Write-Host "Ollama OK. Modelos:" ($tags.models | ForEach-Object { $_.name }) -ForegroundColor Green
} catch {
    Write-Host "Ollama instalado pero API no responde. Inicie la app Ollama desde el menú Inicio." -ForegroundColor Red
    exit 1
}

$Root = Split-Path -Parent $PSScriptRoot
$EnvLocal = Join-Path $Root ".env.local"
$Lines = @(
    "",
    "# LhexIA Operador v0.2 (generado setup_ollama_sd.ps1)",
    "AGENTE_OPERADOR_USE_NEON=1",
    "AGENTE_OLLAMA_ENABLED=1",
    "OLLAMA_BASE_URL=http://127.0.0.1:11434",
    "OLLAMA_MODEL=$Model",
    "OLLAMA_TIMEOUT_SEC=120"
)
if (Test-Path $EnvLocal) {
    $content = Get-Content $EnvLocal -Raw
    if ($content -notmatch 'AGENTE_OLLAMA_ENABLED') {
        Add-Content -Path $EnvLocal -Value ($Lines -join "`n")
        Write-Host "Variables añadidas a .env.local" -ForegroundColor Green
    } else {
        Write-Host ".env.local ya tiene AGENTE_OLLAMA_ENABLED — revise manualmente." -ForegroundColor Yellow
    }
} else {
    Write-Host "Cree .env.local con DATABASE_URL (Neon) y pegue:" -ForegroundColor Yellow
    $Lines | ForEach-Object { Write-Host $_ }
}

Write-Host ""
Write-Host "En .env.local debe existir NEON_DATABASE_URL (misma Neon que Render)." -ForegroundColor Yellow
Write-Host "AGENTE_OPERADOR_USE_NEON=1 hace que el worker use Neon, no Postgres local." -ForegroundColor Yellow
Write-Host ""
Write-Host "Diagnóstico:" -ForegroundColor Cyan
Write-Host "  cd `"$Root`""
Write-Host "  python scripts/verificar_operador_ollama.py"
Write-Host ""
Write-Host "Ciclo completo (scan + enrich):" -ForegroundColor Cyan
Write-Host "  python scripts/agente_operador_ciclo.py"
Write-Host ""
Write-Host "Tarea programada (cada 10 min):" -ForegroundColor Cyan
Write-Host "  powershell -ExecutionPolicy Bypass -File `"$Root\scripts\registrar_tarea_operador_windows.ps1`""
