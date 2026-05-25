# Registra tarea Windows: LhexIA Operador cada 10 minutos (scan + enrich Ollama)
param(
    [int]$IntervalMinutes = 10
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Python) { $Python = (Get-Command py -ErrorAction SilentlyContinue).Source; $PyArgs = "-3" }
if (-not $Python) {
    Write-Host "Python no encontrado en PATH." -ForegroundColor Red
    exit 1
}

$TaskName = "LhexIA-Operador-SD"
$Script = Join-Path $Root "scripts\agente_operador_ciclo.py"
$Action = New-ScheduledTaskAction -Execute $Python -Argument "`"$Script`"" -WorkingDirectory $Root
# RepetitionDuration max ~10 anos (MaxValue rompe el XML de tareas en algunas builds de Windows)
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) -RepetitionDuration (New-TimeSpan -Days 3650)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null
Write-Host "Tarea '$TaskName' registrada - cada $IntervalMinutes min." -ForegroundColor Green
Write-Host ('Probar ahora: Start-ScheduledTask -TaskName ' + $TaskName)
