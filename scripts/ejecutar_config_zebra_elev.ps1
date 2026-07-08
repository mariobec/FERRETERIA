$script = Join-Path $PSScriptRoot 'configurar_zebra_red.ps1'
$log = Join-Path $PSScriptRoot '_zebra_red_setup.log'
Write-Host 'Configurando Zebra en red (acepte UAC si aparece)...'
$p = Start-Process -FilePath powershell.exe -ArgumentList @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $script
) -Verb RunAs -Wait -PassThru
Write-Host "Exit elevado: $($p.ExitCode)"
if (Test-Path $log) {
    Write-Host '--- LOG ---'
    Get-Content $log -Encoding UTF8
}
