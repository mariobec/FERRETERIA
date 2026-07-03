# Acceso directo escritorio -> INSTALACION\LhexIA_Centro_Control.exe
param(
    [string]$ErpRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$InstalacionDir = (Join-Path (Split-Path -Parent $PSScriptRoot) 'INSTALACION'),
    [string]$Desktop = [Environment]::GetFolderPath('Desktop')
)

$exe = Join-Path $InstalacionDir 'LhexIA_Centro_Control.exe'
if (-not (Test-Path -LiteralPath $exe)) {
    Write-Error "No se encontro $exe — compile o copie el Centro de Control en INSTALACION\"
    exit 1
}

$lnk = Join-Path $Desktop 'LhexIA ERP - INSTALACION.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($lnk)
$shortcut.TargetPath = $exe
$shortcut.WorkingDirectory = $InstalacionDir
$shortcut.Description = 'LhexIA ERP — Centro de Control (carpeta INSTALACION)'
$shortcut.Save()
Write-Host "[OK] $lnk"
