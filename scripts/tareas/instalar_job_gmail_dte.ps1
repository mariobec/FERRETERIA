# Instala tarea programada Windows - Gmail DTE (etiquetar + import SD)
#   powershell -ExecutionPolicy Bypass -File scripts\tareas\instalar_job_gmail_dte.ps1

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Bat = Join-Path $RepoRoot 'scripts\tareas\gmail_dte_job.bat'
$TaskName = 'LhexIA-Gmail-DTE-SantoDomingo'

if (-not (Test-Path $Bat)) {
    Write-Error "No se encuentra $Bat"
}

$Action = New-ScheduledTaskAction `
    -Execute 'wscript.exe' `
    -Argument "`"$(Join-Path $RepoRoot 'scripts\tareas\run_job_hidden.vbs')`" `"scripts\tareas\gmail_dte_job.bat`"" `
    -WorkingDirectory $RepoRoot
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Days 3650)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1) -Hidden

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description 'Gmail DTE SD: etiqueta RUT 8054120-1 e importa recepciones documentales. Solo carpeta DTE.' -Force | Out-Null

Write-Host "OK Tarea registrada: $TaskName"
Write-Host "  Cada 30 min"
Write-Host "  Script: $Bat"
Write-Host "  Log: $RepoRoot\logs\"
Write-Host ""
Write-Host "Quitar: Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
