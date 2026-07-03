# Migracion DTE 3 anos — ejecuta lotes hasta completar o Ctrl+C
#   powershell -ExecutionPolicy Bypass -File scripts\tareas\migracion_dte_3_anios.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\tareas\migracion_dte_3_anios.ps1 -Modo importar

param(
    [ValidateSet('etiquetar', 'importar', 'todo')]
    [string]$Modo = 'etiquetar',
    [int]$Lote = 200,
    [int]$Anios = 3,
    [int]$MaxCiclos = 500
)

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Bat = Join-Path $PSScriptRoot 'migracion_dte_3_anios.bat'
$Log = Join-Path $RepoRoot 'logs\migracion_dte_3anios.log'

Write-Host "Migracion DTE ultimos $Anios anos · modo=$Modo · lote=$Lote"
Write-Host "Log: $Log"
Write-Host "Detener: Ctrl+C"
Write-Host ""

$ciclo = 0
while ($ciclo -lt $MaxCiclos) {
    $ciclo++
    Write-Host "--- Ciclo $ciclo ---"
    if ($Modo -eq 'etiquetar') {
        & cmd /c "`"$Bat`""
    } elseif ($Modo -eq 'importar') {
        & cmd /c "`"$Bat`" importar"
    } else {
        & cmd /c "`"$Bat`" todo"
    }
    if ($LASTEXITCODE -ge 2) {
        Write-Host "Error critico, deteniendo."
        break
    }
    Start-Sleep -Seconds 3
}

Write-Host "Fin migracion ($ciclo ciclos). Revise $Log"
