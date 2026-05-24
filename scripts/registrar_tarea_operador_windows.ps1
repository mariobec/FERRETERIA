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
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) -RepetitionDuration ([TimeSpan]::MaxValue)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null
Write-Host "Tarea '$TaskName' registrada — cada $IntervalMinutes min." -ForegroundColor Green
Write-Host "Probar ahora: Start-ScheduledTask -TaskName '$TaskName'"
