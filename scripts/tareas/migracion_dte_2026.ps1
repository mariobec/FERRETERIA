# Migracion DTE 2026 - ejecuta lotes hasta MaxCiclos
# powershell -ExecutionPolicy Bypass -File scripts\tareas\migracion_dte_2026.ps1

param([int]$Lote = 200, [int]$MaxCiclos = 100)
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Bat = Join-Path $PSScriptRoot 'migracion_dte_2026.bat'
$Log = Join-Path $RepoRoot 'logs\migracion_dte_2026.log'

Write-Host "Migracion DTE 2026 - lote $Lote - max $MaxCiclos ciclos"
Write-Host "Log: $Log"
Write-Host "Ctrl+C para detener"
Write-Host ""

for ($i = 1; $i -le $MaxCiclos; $i++) {
    Write-Host "--- Ciclo $i ---"
    & cmd /c "`"$Bat`""
    if ($LASTEXITCODE -ge 2) { Write-Host "Error critico"; break }
    Start-Sleep -Seconds 5
}
Write-Host "Fin. Revise $Log y el visor /recepciones/visor"
