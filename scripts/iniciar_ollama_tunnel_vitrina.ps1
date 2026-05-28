# Túnel Cloudflare rápido: expone Ollama local (11434) a internet para Liz en Render.
# Requiere cloudflared en PATH: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
# La URL cambia cada vez que reinicia el túnel (demo). Para URL fija ver docs/VITRINA_OLLAMA_PRODUCCION.md

$ErrorActionPreference = "Stop"

Write-Host "=== Liz vitrina — túnel Ollama → Render ===" -ForegroundColor Cyan

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama no está instalado. Ejecute primero scripts\setup_ollama_sd.ps1" -ForegroundColor Red
    exit 1
}

try {
    $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 8
    Write-Host "Ollama local OK. Modelos:" ($tags.models | ForEach-Object { $_.name }) -ForegroundColor Green
} catch {
    Write-Host "Ollama no responde en 127.0.0.1:11434. Abra la app Ollama." -ForegroundColor Red
    exit 1
}

if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    Write-Host "cloudflared no está en PATH." -ForegroundColor Yellow
    Write-Host "Descargue: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
    Write-Host "Alternativa: Tailscale Funnel → tailscale funnel 11434"
    exit 1
}

Write-Host ""
Write-Host "Iniciando túnel (deje esta ventana abierta)..." -ForegroundColor Yellow
Write-Host "Cuando aparezca la URL https://....trycloudflare.com copiela a Render:" -ForegroundColor Yellow
Write-Host "  VITRINA_OLLAMA_ENABLED=1"
Write-Host "  VITRINA_OLLAMA_BASE_URL=<esa URL sin barra final>"
Write-Host ""

& cloudflared tunnel --url http://127.0.0.1:11434
