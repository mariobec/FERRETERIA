# Instala tarea programada Windows — Gmail transferencias banco → bandeja caja
#   powershell -ExecutionPolicy Bypass -File scripts\tareas\instalar_job_gmail_transferencias.ps1

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Vbs = Join-Path $RepoRoot 'scripts\tareas\run_job_hidden.vbs'
$Bat = Join-Path $RepoRoot 'scripts\tareas\gmail_transferencias_job.bat'
$TaskName = 'LhexIA-Gmail-Transferencias-SantoDomingo'

if (-not (Test-Path $Bat)) {
    Write-Error "No se encuentra $Bat"
}
if (-not (Test-Path $Vbs)) {
    Write-Error "No se encuentra $Vbs"
}

$IntervalMin = 2
# wscript + VBS windowStyle 0 + pythonw en .bat = sin ventana de consola
$Action = New-ScheduledTaskAction `
    -Execute 'wscript.exe' `
    -Argument "`"$Vbs`" `"scripts\tareas\gmail_transferencias_job.bat`"" `
    -WorkingDirectory $RepoRoot
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMin) -RepetitionDuration (New-TimeSpan -Days 3650)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 8) -MultipleInstances IgnoreNew -Hidden

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description 'Gmail TRF: etiqueta Transferencias-Banco y sincroniza /caja/transferencias cada 2 min (sin ventana).' -Force | Out-Null

Write-Host "OK Tarea registrada (sin consola): $TaskName"
Write-Host "  Cada $IntervalMin min · ejecucion oculta (wscript + pythonw)"
Write-Host "  Script: $Bat"
Write-Host "  Log: $RepoRoot\logs\gmail_transferencias_job_*.log"
Write-Host ""
Write-Host "Quitar: Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
